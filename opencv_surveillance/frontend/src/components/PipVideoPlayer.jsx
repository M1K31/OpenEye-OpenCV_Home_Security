// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useEffect, useRef, useState } from 'react';

/**
 * PipVideoPlayer Component
 *
 * Uses the native Web Picture-in-Picture API to display camera streams
 * in a system-level floating window.
 *
 * Note: MJPEG streams work in video elements in most browsers.
 * The video element is hidden and only shown in PiP mode.
 */
const PipVideoPlayer = ({ camera, onReady, onClose }) => {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const imgRef = useRef(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const animationFrameRef = useRef(null);
  const streamRef = useRef(null);

  // Detect Safari browser
  const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);

  useEffect(() => {
    // Safari doesn't support canvas.captureStream() reliably
    if (isSafari) {
      setIsLoading(false);
      setError('Picture-in-Picture is not fully supported in Safari. Please use Chrome, Edge, or Firefox for this feature.');
      if (onClose) {
        setTimeout(() => onClose(), 3000); // Auto-close after showing error
      }
      return;
    }

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const img = imgRef.current;

    if (!video || !canvas || !img) return;

    // Setup canvas dimensions
    canvas.width = 640;
    canvas.height = 480;
    const ctx = canvas.getContext('2d');

    // Function to draw MJPEG frames to canvas
    const drawFrame = () => {
      if (img.complete && img.naturalHeight !== 0) {
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      }
      animationFrameRef.current = requestAnimationFrame(drawFrame);
    };

    // Start drawing frames
    drawFrame();

    // Capture canvas stream and set it as video source
    try {
      const canvasStream = canvas.captureStream(30); // 30 FPS
      video.srcObject = canvasStream;
      streamRef.current = canvasStream;

      video.play().then(() => {
        setIsLoading(false);
        // Notify parent that video is ready for PiP
        if (onReady) {
          onReady(video);
        }
      }).catch(err => {
        console.error('Failed to play video:', err);
        setError('Failed to start video stream');
      });

    } catch (err) {
      console.error('Failed to capture canvas stream:', err);
      setError('Failed to create video stream');
    }

    // Handle image load errors
    const handleImgError = () => {
      console.error('MJPEG stream failed to load');
      setError('Camera stream unavailable');
    };

    img.addEventListener('error', handleImgError);

    // Cleanup function
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
      if (video.srcObject) {
        video.srcObject = null;
      }
      img.removeEventListener('error', handleImgError);
    };
  }, [camera, onReady]);

  // Handle when user closes PiP from browser controls
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleLeavePip = () => {
      if (onClose) {
        onClose();
      }
    };

    video.addEventListener('leavepictureinpicture', handleLeavePip);

    return () => {
      video.removeEventListener('leavepictureinpicture', handleLeavePip);
    };
  }, [onClose]);

  return (
    <div style={{ position: 'absolute', left: '-9999px', top: '-9999px' }}>
      {/* Hidden image element that loads the MJPEG stream */}
      <img
        ref={imgRef}
        src={`/api/cameras/${camera.camera_id}/stream`}
        alt="Camera stream"
        style={{ display: 'none' }}
        crossOrigin="anonymous"
      />

      {/* Hidden canvas that converts MJPEG to video frames */}
      <canvas
        ref={canvasRef}
        style={{ display: 'none' }}
      />

      {/* Hidden video element for PiP */}
      <video
        ref={videoRef}
        muted
        playsInline
        style={{ width: '640px', height: '480px' }}
        title={`${camera.name || camera.camera_id} - Picture in Picture`}
      />

      {/* Loading/Error indicators (for debugging) */}
      {isLoading && (
        <div style={{ position: 'fixed', top: '10px', right: '10px', background: 'rgba(0,0,0,0.8)', color: 'white', padding: '8px', borderRadius: '4px', zIndex: 9999 }}>
          Loading PiP...
        </div>
      )}
      {error && (
        <div style={{ position: 'fixed', top: '10px', right: '10px', background: 'rgba(255,0,0,0.8)', color: 'white', padding: '8px', borderRadius: '4px', zIndex: 9999 }}>
          {error}
        </div>
      )}
    </div>
  );
};

export default PipVideoPlayer;
