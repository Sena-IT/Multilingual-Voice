// frontend/src/App.js
import React, { useEffect, useState, useRef, useCallback } from "react";
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Settings,
  LogOut,
  BarChart2,
  Play,
} from "react-feather";
import "./App.css";
import ClientWebRTCTransport from "./components/transport/client_transport";
import { useRTVIWebRTC } from "./components/transport/client_transport"; // Import the RTVI hook
import WaveformVisualizer from "./components/WaveformVisualizer";

const App = () => {
  const [connected, setConnected] = useState(false);
  const [micEnabled, setMicEnabled] = useState(true);
  const [botIsTalking, setBotIsTalking] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [userIsSpeaking, setUserIsSpeaking] = useState(false);
  const [timer, setTimer] = useState("0m 0s");
  const [showStats, setShowStats] = useState(false); // Toggle for stats panel
  const [language, setLanguage] = useState("en");
  const [isLanguageToggleDisabled, setIsLanguageToggleDisabled] =
    useState(false);
  const transportRef = useRef(null);
  const audioRef = useRef(null);
  const timerIntervalRef = useRef(null);

  // === Web Audio API Refs ===
  const audioContextRef = useRef(null);
  const localAudioAnalyserRef = useRef(null);
  const remoteAudioAnalyserRef = useRef(null);
  const localAudioSourceRef = useRef(null);
  const remoteAudioSourceRef = useRef(null);
  const animationFrameRef = useRef(null);

  // === RTVI Hook ===
  const { metrics: rtviMetrics, connectionStatus: rtviStatus } =
    useRTVIWebRTC();

  // Initialize Audio Context Function
  const initializeAudioContext = useCallback(() => {
    if (!audioContextRef.current) {
      try {
        audioContextRef.current = new (window.AudioContext ||
          window.webkitAudioContext)();
        console.log("AudioContext initialized");
      } catch (e) {
        console.error("Web Audio API is not supported in this browser", e);
      }
    }
  }, []);

  // Cleanup Audio Context and Nodes
  const cleanupAudioNodes = useCallback(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    localAudioSourceRef.current?.disconnect();
    remoteAudioSourceRef.current?.disconnect();
    localAudioAnalyserRef.current = null;
    remoteAudioAnalyserRef.current = null;
    localAudioSourceRef.current = null;
    remoteAudioSourceRef.current = null;
    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      console.log("Audio nodes disconnected/nulled");
    }
  }, []);

  useEffect(() => {
    initializeAudioContext();

    const transport = new ClientWebRTCTransport();
    transportRef.current = transport;

    transport.initialize();
    transport.initDevices().catch((e) => {
      console.error("Failed to initialize devices:", e);
    });

    transport.on("stateChange", (state) => {
      console.log("State changed:", state);
      if (state === "connected") {
        setConnected(true);
        setIsLanguageToggleDisabled(true);
        startTimer();
      } else if (state === "disconnected") {
        setConnected(false);
        setIsLanguageToggleDisabled(false);
        stopTimer();
        setIsReady(false);
        setBotIsTalking(false);
        cleanupAudioNodes();
      }
    });

    // === Handle Remote Bot Audio Track ===
    transport.on("track", (event) => {
      console.log("Received remote audio track:", event);
      if (audioRef.current && event.streams && event.streams[0]) {
        const remoteStream = event.streams[0];
        audioRef.current.srcObject = remoteStream;
        audioRef.current
          .play()
          .catch((err) => console.error("Audio playback error:", err));

        // Setup Analyser for Remote Audio
        if (
          audioContextRef.current &&
          audioContextRef.current.state === "running" &&
          remoteStream.getAudioTracks().length > 0
        ) {
          if (!remoteAudioAnalyserRef.current) {
            remoteAudioAnalyserRef.current =
              audioContextRef.current.createAnalyser();
            remoteAudioAnalyserRef.current.fftSize = 256;
            console.log("Remote audio analyser created");
          }
          // Disconnect previous source if exists
          remoteAudioSourceRef.current?.disconnect();

          remoteAudioSourceRef.current =
            audioContextRef.current.createMediaStreamSource(remoteStream);
          try {
            remoteAudioSourceRef.current.connect(
              remoteAudioAnalyserRef.current
            );
            console.log("Remote audio source connected to analyser");
          } catch (error) {
            console.error("Error connecting remote audio source:", error);
          }
        } else {
          console.warn(
            "Could not setup remote analyser: AudioContext not running or no audio tracks."
          );
        }
      } else {
        console.warn(
          "Could not play remote audio: audioRef or stream missing."
        );
      }
    });

    transport.on("botStartedSpeaking", () => {
      console.log("Bot started speaking");
      setBotIsTalking(true);
    });

    transport.on("botStoppedSpeaking", () => {
      console.log("Bot stopped speaking");
      setBotIsTalking(false);
    });

    transport.on("botReady", () => {
      console.log("Bot is ready");
      setIsReady(true);
    });

    transport.on("error", (error) => {
      console.error("Transport error:", error);
    });

    // === Setup Local Mic Activity Detection & Analyser ===
    const setupMicAnalyser = async () => {
      if (
        !micEnabled ||
        !transportRef.current?.localTrack ||
        !audioContextRef.current ||
        audioContextRef.current.state !== "running"
      ) {
        setUserIsSpeaking(false);
        if (!micEnabled) {
          localAudioSourceRef.current?.disconnect();
          localAudioSourceRef.current = null;
          localAudioAnalyserRef.current = null;
          if (animationFrameRef.current) {
            cancelAnimationFrame(animationFrameRef.current);
            animationFrameRef.current = null;
          }
        }
        return;
      }

      try {
        if (!localAudioAnalyserRef.current) {
          localAudioAnalyserRef.current =
            audioContextRef.current.createAnalyser();
          localAudioAnalyserRef.current.fftSize = 256;
          console.log("Local audio analyser created");
        }

        let needsNewSource = !localAudioSourceRef.current;
        if (
          localAudioSourceRef.current &&
          localAudioSourceRef.current.mediaStream.getAudioTracks()[0] !==
            transportRef.current.localTrack
        ) {
          localAudioSourceRef.current.disconnect();
          needsNewSource = true;
          console.log("Local audio track changed, creating new source.");
        }

        if (needsNewSource) {
          const stream = new MediaStream([transportRef.current.localTrack]);
          localAudioSourceRef.current =
            audioContextRef.current.createMediaStreamSource(stream);
          localAudioSourceRef.current.connect(localAudioAnalyserRef.current);
          console.log("Local audio source connected to analyser");
        }

        if (localAudioAnalyserRef.current) {
          const bufferLength = localAudioAnalyserRef.current.frequencyBinCount;
          const dataArray = new Uint8Array(bufferLength);

          const detectSpeech = () => {
            if (!localAudioAnalyserRef.current) {
              setUserIsSpeaking(false);
              return;
            }
            localAudioAnalyserRef.current.getByteTimeDomainData(dataArray);
            let sumSquares = 0.0;
            for (const amplitude of dataArray) {
              const scaledAmplitude = amplitude / 128.0 - 1.0;
              sumSquares += scaledAmplitude * scaledAmplitude;
            }
            const rms = Math.sqrt(sumSquares / bufferLength);

            const speakingThreshold = 0.02;
            const isSpeaking = rms > speakingThreshold;

            setUserIsSpeaking((prev) =>
              isSpeaking !== prev ? isSpeaking : prev
            );

            animationFrameRef.current = requestAnimationFrame(detectSpeech);
          };

          if (animationFrameRef.current) {
            cancelAnimationFrame(animationFrameRef.current);
          }
          detectSpeech();
        } else {
          setUserIsSpeaking(false);
        }
      } catch (err) {
        console.error("Error setting up mic analyser:", err);
        setUserIsSpeaking(false);
        localAudioSourceRef.current?.disconnect();
        localAudioSourceRef.current = null;
        localAudioAnalyserRef.current = null;
        if (animationFrameRef.current) {
          cancelAnimationFrame(animationFrameRef.current);
          animationFrameRef.current = null;
        }
      }
    };

    setupMicAnalyser();

    return () => {
      transport.disconnect();
      stopTimer();
      cleanupAudioNodes();
      if (audioContextRef.current?.state !== "closed") {
        // Consider closing context fully on unmount if appropriate
      }
    };
  }, [initializeAudioContext, cleanupAudioNodes, micEnabled]);

  const startTimer = () => {
    const startTime = Date.now();
    timerIntervalRef.current = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      const minutes = Math.floor(elapsed / 60);
      const seconds = elapsed % 60;
      setTimer(`${minutes}m ${seconds}s`);
    }, 1000);
  };

  const stopTimer = () => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    setTimer("0m 0s");
  };

  const toggleMic = () => {
    setMicEnabled((prev) => {
      const newState = !prev;
      transportRef.current.enableMic(newState);
      return newState;
    });
  };

  const endSession = () => {
    transportRef.current.disconnect();
  };

  const handleLanguageChange = (event) => {
    setLanguage(event.target.checked ? "ta" : "en");
  };

  const renderRTVIMetrics = () => {
    if (!rtviMetrics)
      return (
        <div className="metrics-placeholder">Waiting for metrics data...</div>
      );

    return (
      <div className="rtvi-metrics">
        {/* TTFB Metrics */}
        {rtviMetrics.ttfb && rtviMetrics.ttfb.length > 0 && (
          <div className="metric-section">
            <h4>Time to First Byte</h4>
            {rtviMetrics.ttfb.map((m, i) => (
              <div key={i} className="metric-item">
                <span className="metric-label">{m.processor}:</span>
                <span className="metric-value">
                  {(m.value || 0).toFixed(3)}s
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Processing Metrics */}
        {rtviMetrics.processing && rtviMetrics.processing.length > 0 && (
          <div className="metric-section">
            <h4>Processing Time</h4>
            {rtviMetrics.processing.map((m, i) => (
              <div key={i} className="metric-item">
                <span className="metric-label">{m.processor}:</span>
                <span className="metric-value">
                  {(m.value || 0).toFixed(3)}s
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Token Usage */}
        {rtviMetrics.tokens && rtviMetrics.tokens.length > 0 && (
          <div className="metric-section">
            <h4>Token Usage</h4>
            {rtviMetrics.tokens.map((t, i) => (
              <div key={i} className="metric-group">
                <div className="metric-item">
                  <span className="metric-label">Prompt Tokens:</span>
                  <span className="metric-value">{t.prompt_tokens || 0}</span>
                </div>
                <div className="metric-item">
                  <span className="metric-label">Completion Tokens:</span>
                  <span className="metric-value">
                    {t.completion_tokens || 0}
                  </span>
                </div>
                <div className="metric-item">
                  <span className="metric-label">Total:</span>
                  <span className="metric-value">{t.total_tokens || 0}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Character Usage */}
        {rtviMetrics.characters && rtviMetrics.characters.length > 0 && (
          <div className="metric-section">
            <h4>TTS Character Usage</h4>
            {rtviMetrics.characters.map((c, i) => (
              <div key={i} className="metric-item">
                <span className="metric-label">Characters:</span>
                <span className="metric-value">{c.value || 0}</span>
              </div>
            ))}
          </div>
        )}

        {/* RTVI Connection Status */}
        <div className="metric-section">
          <h4>RTVI Status</h4>
          <div className="metric-item">
            <span className="metric-label">Connection:</span>
            <span className={`metric-value ${rtviStatus}`}>{rtviStatus}</span>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="App">
      <div className="main-content">
        {/* Interaction Card */}
        <div className="interaction-card">
          <div className="card-title">Sena Assistant</div>
          <div className="transcription-area">
            <p>Transcription will appear here...</p>
          </div>
          <div className="status-indicator">
            {!isReady ? (
              <div className="dots">
                <span></span>
                <span></span>
                <span></span>
                <span></span>
                <span></span>
              </div>
            ) : botIsTalking && remoteAudioAnalyserRef.current ? (
              <WaveformVisualizer
                analyserNode={remoteAudioAnalyserRef.current}
              />
            ) : (
              <div style={{ height: "40px", width: "80px" }}></div>
            )}
          </div>
          <button
            className={`mic-button ${!micEnabled ? "disabled" : ""}`}
            onClick={toggleMic}
            disabled={!connected || !isReady}
          >
            {micEnabled ? <Mic size={32} /> : <MicOff size={32} />}
          </button>
          <div className="user-status-container">
            {userIsSpeaking && localAudioAnalyserRef.current ? (
              <WaveformVisualizer
                analyserNode={localAudioAnalyserRef.current}
                height={30}
                color="var(--success-color)"
              />
            ) : (
              <div className="mic-status-text">
                {micEnabled ? "Microphone On" : "Microphone Off"}
              </div>
            )}
          </div>
        </div>

        {/* Metrics Card */}
        <div className="metrics-card">
          <button
            className="metrics-toggle-button"
            onClick={() => setShowStats(!showStats)}
            aria-expanded={showStats}
            aria-controls="stats-container-content"
          >
            {showStats ? "Hide Metrics" : "Show Metrics"}
          </button>
          {showStats && (
            <div className="stats-container" id="stats-container-content">
              {renderRTVIMetrics()}
            </div>
          )}
          {!showStats && (
            <div className="metrics-placeholder">
              Metrics are hidden. Click the button above to display real-time
              statistics.
            </div>
          )}
        </div>
      </div>

      {/* Bottom Controls Container */}
      <div className="controls-container">
        {/* Left side: Language Toggle and Timer */}
        <div className="connection-info">
          {!connected && (
            <div className="language-toggle-container">
              <span className="toggle-label">EN</span>
              <label className="language-toggle-switch">
                <input
                  type="checkbox"
                  checked={language === "ta"}
                  onChange={handleLanguageChange}
                  disabled={isLanguageToggleDisabled}
                />
                <span className="slider round"></span>
              </label>
              <span className="toggle-label">TA</span>
            </div>
          )}
          {connected && <span className="timer">{timer}</span>}
        </div>

        {/* Right side: Action Buttons */}
        <div className="action-buttons">
          <button
            className={`control-button ${!micEnabled ? "active-muted" : ""}`}
            onClick={toggleMic}
            title={micEnabled ? "Mute Microphone" : "Unmute Microphone"}
            disabled={!connected || !isReady}
          >
            {micEnabled ? <Volume2 size={20} /> : <VolumeX size={20} />}
          </button>
          <button
            className="control-button"
            onClick={() =>
              console.log("Settings button clicked (not implemented)")
            }
            title="Settings"
          >
            <Settings size={20} />
          </button>

          <button
            className={`control-button ${connected ? "disconnect-active" : ""}`}
            onClick={async () => {
              if (connected) {
                endSession();
              } else {
                try {
                  console.log(
                    "Connect button clicked. Resuming AudioContext if needed..."
                  );
                  if (
                    audioContextRef.current &&
                    audioContextRef.current.state === "suspended"
                  ) {
                    await audioContextRef.current.resume();
                    console.log("AudioContext resumed.");
                  }
                  console.log(
                    `Attempting to connect with language: ${language}...`
                  );
                  await transportRef.current.connect(language);
                  console.log("transport.connect() call completed.");
                } catch (error) {
                  console.error("Connection failed inside onClick:", error);
                }
              }
            }}
            title={connected ? "End Session" : "Connect"}
          >
            {connected ? (
              <LogOut size={20} color="var(--error-color)" />
            ) : (
              <Play size={20} />
            )}
          </button>
        </div>
      </div>

      {/* Hidden audio element for playback */}
      <audio ref={audioRef} playsInline style={{ display: "none" }} />
    </div>
  );
};

export default App;
