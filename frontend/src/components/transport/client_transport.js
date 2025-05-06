// frontend/src/transport/client_transport.js (updated)
import React, { useState, useRef, useEffect } from "react";

class ClientWebRTCTransport {
  constructor(serverUrl = "http://localhost:7860") {
    this.serverUrl = serverUrl;
    this.pc = null;
    this.listeners = new Map();
    this.remoteTracks = [];
    this.localTrack = null;
    this._state = "disconnected";
    this.selectedMic = null;
    this.mics = [];
    this.dataChannel = null;
    this.onMessage = null;
  }

  get state() {
    return this._state;
  }

  set state(state) {
    if (this._state === state) return;
    this._state = state;
    this.emit("stateChange", state);
  }

  initializePeerConnection() {
    if (this.pc) {
      this.pc.close();
    }
    this.pc = new RTCPeerConnection({
      iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
    });

    // Handle incoming bot audio
    this.pc.ontrack = (event) => {
      this.remoteTracks = event.streams[0].getTracks();
      this.emit("track", event);
      this.emit("botStartedSpeaking");

      // Listen for track ending
      event.track.onended = () => {
        this.emit("botStoppedSpeaking");
      };
    };

    // Handle connection state changes
    this.pc.onconnectionstatechange = () => {
      const state = this.pc?.connectionState;
      console.log(`[Transport] Connection state: ${state}`);
      if (state === "connecting") {
        this.state = "connecting";
      } else if (state === "connected") {
        if (this.pc.sctp) {
          console.log("[Transport] SCTP transport available:", this.pc.sctp);
        }
        this.state = "connected";
        this.emit("botReady");
      } else if (
        state === "disconnected" ||
        state === "failed" ||
        state === "closed"
      ) {
        this.state = "disconnected";
        this.remoteTracks = [];
        this.localTrack = null;
      }
      this.emit("stateChange", this.state);
    };

    // Handle ICE candidates (optional for now, can be extended later)
    this.pc.onicecandidate = (event) => {
      if (event.candidate) {
        this.emit("iceCandidate", event.candidate);
      }
    };

    // Listen for data channel events (e.g., metrics)
    this.pc.ondatachannel = (event) => {
      const dataChannel = event.channel;
      console.log(
        `[Transport] ondatachannel event received. Channel Label: ${dataChannel.label}, State: ${dataChannel.readyState}`
      );
      console.log(`[Transport] All data channels:`, event);

      if (dataChannel.label === "rtvi-ai") {
        dataChannel.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            console.log("[Transport] Received rtvi-ai message:", message);
            if (message.type === "metrics") {
              this.emit("metrics", message.data);
            }

            if (this.onMessage) {
              this.onMessage({ data: event.data });
            }
          } catch (e) {
            console.error("[Transport] Failed to parse RTVI message:", e);
          }
        };
        dataChannel.onopen = () =>
          console.log("[Transport] Metrics data channel opened");
        dataChannel.onclose = () =>
          console.log("[Transport] Metrics data channel closed");
        dataChannel.onerror = (error) =>
          console.error("[Transport] Metrics data channel error:", error);
      } else {
        console.log(
          `[Transport] Data channel with label '${dataChannel.label}' ignored.`
        );
        dataChannel.onmessage = (event) => {
          console.log(
            `[Transport] Received message on unexpected channel '${dataChannel.label}':`,
            event.data
          );
        };
        dataChannel.onopen = () =>
          console.log(`[Transport] Data channel '${dataChannel.label}' opened`);
        dataChannel.onclose = () =>
          console.log(`[Transport] Data channel '${dataChannel.label}' closed`);
        dataChannel.onerror = (error) =>
          console.error(
            `[Transport] Data channel '${dataChannel.label}' error:`,
            error
          );
      }
    };
  }

  async start() {
    await this.initialize();
    await this.initDevices();
  }

  async stop() {
    await this.disconnect();
  }

  async initialize() {
    this.initializePeerConnection();
    this.state = "disconnected";
  }

  async initDevices() {
    this.state = "initializing";

    const devices = await navigator.mediaDevices.enumerateDevices();
    this.mics = devices.filter((d) => d.kind === "audioinput");

    this.emit("onAvailableMicsUpdated", this.mics);

    if (this.mics.length > 0) {
      this.selectedMic = this.mics[0];
      this.emit("onMicUpdated", this.selectedMic);

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: this.selectedMic
            ? { deviceId: { exact: this.selectedMic.deviceId } }
            : true,
        });
        this.localTrack = stream.getAudioTracks()[0];
      } catch (error) {
        console.error("Failed to pre-initialize audio in initDevices:", error);
        this.localTrack = null;
      }
    }

    this.state = "initialized";
  }

  async connect(language) {
    if (!this.pc) {
      this.initializePeerConnection();
    }

    try {
      this.state = "connecting";

      console.log(
        "[Transport] Checking localTrack before getUserMedia fallback. localTrack:",
        this.localTrack,
        "Selected Mic:",
        this.selectedMic
      );
      if (!this.localTrack) {
        console.log(
          "[Transport] localTrack is missing, attempting getUserMedia fallback."
        );
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: this.selectedMic
            ? { deviceId: { exact: this.selectedMic.deviceId } }
            : true,
        });
        this.localTrack = stream.getAudioTracks()[0];
      }

      if (this.localTrack) {
        this.pc.addTransceiver(this.localTrack, { direction: "sendrecv" });
      } else {
        throw new Error("No local audio track available");
      }

      const offer = await this.pc.createOffer();
      await this.pc.setLocalDescription(offer);

      const response = await fetch(`${this.serverUrl}/api/offer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sdp: offer.sdp,
          type: offer.type,
          language: language,
        }),
      });

      if (!response.ok) {
        this.state = "error";
        throw new Error(`Server responded with ${response.status}`);
      }

      const answer = await response.json();
      await this.pc.setRemoteDescription(answer);

      this.state = "connected";
    } catch (error) {
      this.state = "error";
      console.error("[Transport] Error during connect:", error);
      this.emit("error", error);
      throw error;
    }
  }

  async disconnect() {
    if (this.pc) {
      this.state = "disconnecting";
      this.pc.close();
      this.pc = null;
      this.remoteTracks = [];
      if (this.localTrack) {
        this.localTrack.stop();
        this.localTrack = null;
      }
      this.selectedMic = null;
      this.state = "disconnected";
    }
  }

  enableMic(enabled) {
    if (this.localTrack) {
      this.localTrack.enabled = enabled;
    }
  }

  async updateMic(deviceId) {
    if (!this.pc) {
      this.initializePeerConnection();
    }

    if (!deviceId) {
      if (this.localTrack) {
        this.localTrack.enabled = false;
        this.localTrack.stop();
        this.localTrack = null;
      }
      this.selectedMic = null;
      this.emit("onMicUpdated", null);
      return;
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { deviceId: { exact: deviceId } },
    });
    const newTrack = stream.getAudioTracks()[0];

    const senders = this.pc.getSenders();
    const audioSender = senders.find(
      (sender) => sender.track?.kind === "audio"
    );
    if (audioSender) {
      await audioSender.replaceTrack(newTrack);
    }

    if (this.localTrack) {
      this.localTrack.stop();
    }

    this.localTrack = newTrack;
    newTrack.enabled = true;

    this.selectedMic =
      this.mics.find(
        (d) => d.kind === "audioinput" && d.deviceId === deviceId
      ) || null;
    this.emit("onMicUpdated", this.selectedMic);
  }

  async getAllMics() {
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices.filter((d) => d.kind === "audioinput");
  }

  getTracks() {
    return {
      local: {
        audio: this.localTrack || undefined,
      },
      bot: {
        audio:
          this.remoteTracks.find((track) => track.kind === "audio") ||
          undefined,
      },
    };
  }

  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
  }

  emit(event, data) {
    const callbacks = this.listeners.get(event) || [];
    callbacks.forEach((callback) => callback(data));
  }
}

class RTVIWebRTCClient {
  constructor(transport) {
    this.transport = transport;
    this.isConnected = false;
    this.eventHandlers = {};
    this.metricsCallback = null;

    // Set up message handler
    this.transport.onMessage = this.handleRTVIMessage.bind(this);
  }

  // Set up event handlers
  on(event, handler) {
    if (!this.eventHandlers[event]) {
      this.eventHandlers[event] = [];
    }
    this.eventHandlers[event].push(handler);
  }

  // Set metrics callback
  setMetricsCallback(callback) {
    this.metricsCallback = callback;
  }

  // Handle incoming RTVI messages
  handleRTVIMessage(event) {
    try {
      // RTVI messages are sent through WebRTC data channel
      if (event.data) {
        const message = JSON.parse(event.data);

        if (message.label === "rtvi-ai" && message.type) {
          this.handleRTVIEvent(message);
        }
      }
    } catch (error) {
      console.error("Error handling RTVI message:", error);
    }
  }

  // Handle specific RTVI events
  handleRTVIEvent(message) {
    switch (message.type) {
      case "metrics":
        if (this.metricsCallback) {
          this.metricsCallback(message.data);
        }
        this.emit("metrics", message.data);
        break;

      case "user-transcription":
        this.emit("userTranscript", message.data);
        break;

      case "bot-llm-started":
        this.emit("botLLMStarted");
        break;

      case "bot-llm-stopped":
        this.emit("botLLMStopped");
        break;

      case "bot-started-speaking":
        this.emit("botStartedSpeaking");
        break;

      case "bot-stopped-speaking":
        this.emit("botStoppedSpeaking");
        break;

      case "user-started-speaking":
        this.emit("userStartedSpeaking");
        break;

      case "user-stopped-speaking":
        this.emit("userStoppedSpeaking");
        break;

      default:
        console.log("Unhandled RTVI message type:", message.type);
    }
  }

  // Emit events to registered handlers
  emit(event, data = null) {
    if (this.eventHandlers[event]) {
      this.eventHandlers[event].forEach((handler) => handler(data));
    }
  }

  // Send RTVI messages to the server
  sendMessage(message) {
    if (
      this.transport.dataChannel &&
      this.transport.dataChannel.readyState === "open"
    ) {
      const rtviMessage = {
        label: "rtvi-ai",
        ...message,
      };
      console.log("[RTVI] Sending message:", rtviMessage);
      this.transport.dataChannel.send(JSON.stringify(rtviMessage));
    } else {
      console.warn("[RTVI] Data channel not available for sending message");
    }
  }

  // Client ready notification
  clientReady() {
    this.sendMessage({
      type: "client-ready",
    });
  }

  // Connect to the server
  async connect() {
    try {
      await this.transport.start();

      // Wait for connection to be established
      this.transport.onConnected = () => {
        this.isConnected = true;
        this.clientReady();
      };
    } catch (error) {
      console.error("Connection failed:", error);
      throw error;
    }
  }

  // Disconnect from the server
  disconnect() {
    if (this.transport) {
      this.transport.stop();
    }
    this.isConnected = false;
  }
}

// Usage in your React component
function useRTVIWebRTC() {
  const [metrics, setMetrics] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState("disconnected");
  const clientRef = useRef(null);
  const transportRef = useRef(null);

  useEffect(() => {
    // Create your existing transport
    transportRef.current = new ClientWebRTCTransport();

    transportRef.current.on("stateChange", (state) => {
      setConnectionStatus(state);
    });

    // Create RTVI client with your transport
    clientRef.current = new RTVIWebRTCClient(transportRef.current);

    // Set up metrics handler
    clientRef.current.setMetricsCallback((metricsData) => {
      setMetrics(metricsData);
      console.log("Received metrics:", metricsData);
    });

    // Set up other event handlers
    clientRef.current.on("userTranscript", (data) => {
      console.log("User said:", data.text);
    });

    clientRef.current.on("botStartedSpeaking", () => {
      console.log("Bot started speaking - trying to send test message");
      if (clientRef.current.transport.dataChannel) {
        console.log("Data channel exists, sending test");
        clientRef.current.sendMessage({ type: "test" });
      } else {
        console.log("No data channel available");
      }
    });

    clientRef.current.on("botStoppedSpeaking", () => {
      console.log("Bot stopped speaking");
    });

    // Connect
    const connect = async () => {
      try {
        await clientRef.current.connect();
        setConnectionStatus("connected");
      } catch (error) {
        console.error("Connection failed:", error);
        setConnectionStatus("error");
      }
    };

    connect();

    return () => {
      if (clientRef.current) {
        clientRef.current.disconnect();
      }
    };
  }, []);

  return { metrics, connectionStatus };
}

export default ClientWebRTCTransport;
export { RTVIWebRTCClient, useRTVIWebRTC };
