import React, { useRef, useEffect } from "react";

const WaveformVisualizer = ({
  analyserNode,
  width = 80,
  height = 40,
  color = "var(--primary-color)",
}) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!analyserNode) return;

    const canvas = canvasRef.current;
    const canvasCtx = canvas.getContext("2d");
    const bufferLength = analyserNode.frequencyBinCount; // Use frequencyBinCount
    const dataArray = new Uint8Array(bufferLength);

    let animationFrameId;

    const draw = () => {
      animationFrameId = requestAnimationFrame(draw);

      // Get frequency data
      analyserNode.getByteFrequencyData(dataArray);

      // Clear canvas
      canvasCtx.clearRect(0, 0, width, height);

      // Drawing settings
      canvasCtx.lineWidth = 2; // Width of each bar
      canvasCtx.strokeStyle = color;
      canvasCtx.fillStyle = color;

      const barWidth = (width / bufferLength) * 1.5; // Adjust multiplier for bar density
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        const barHeight = (dataArray[i] / 255) * height; // Scale bar height to canvas height

        // Draw the bar (from bottom up)
        canvasCtx.fillRect(x, height - barHeight, barWidth, barHeight);

        // Move to the next bar position
        x += barWidth + 1; // Add 1 for spacing between bars
      }
    };

    draw();

    // Cleanup function
    return () => {
      cancelAnimationFrame(animationFrameId);
      // Clear canvas on cleanup
      if (canvasCtx) {
        canvasCtx.clearRect(0, 0, width, height);
      }
    };
  }, [analyserNode, width, height, color]); // Rerun effect if analyserNode or dimensions/color change

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      className="waveform-canvas"
    />
  );
};

export default WaveformVisualizer;
