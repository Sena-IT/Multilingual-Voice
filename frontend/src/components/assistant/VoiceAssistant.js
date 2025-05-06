// frontend/src/components/VoiceAssistant.js
import React from "react";
import { useRTVIWebRTC } from "../transport/client_transport";
import MetricsDisplay from "./MetricsDisplay";

function VoiceAssistant() {
  const { metrics, connectionStatus } = useRTVIWebRTC();

  return (
    <div>
      <div>Connection Status: {connectionStatus}</div>
      {metrics && <MetricsDisplay metrics={metrics} />}
    </div>
  );
}

export default VoiceAssistant;
