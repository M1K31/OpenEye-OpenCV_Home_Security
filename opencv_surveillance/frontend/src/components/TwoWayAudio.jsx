// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * Two-Way Audio Component (v3.10.0 - Enhanced)
 *
 * Provides bidirectional audio communication with cameras using WebRTC
 *
 * Features:
 * - WebRTC peer connection management
 * - Push-to-Talk mode for easier conversations
 * - Volume control for incoming audio
 * - Real-time audio level indicators
 * - Browser autoplay fix with explicit user interaction
 * - Comprehensive audio diagnostics
 * - Microphone/speaker permission handling
 * - Error handling and recovery
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { logger } from '../utils/logger';
import './TwoWayAudio.css';

const TwoWayAudio = ({ cameraId }) => {
  // Connection states
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState(null);
  const [audioPlaybackBlocked, setAudioPlaybackBlocked] = useState(false);

  // Push-to-Talk mode
  const [pttMode, setPttMode] = useState(false);
  const [pttActive, setPttActive] = useState(false);

  // Volume control
  const [volume, setVolume] = useState(0.8);

  // Audio level indicators
  const [micLevel, setMicLevel] = useState(0);
  const [remoteLevel, setRemoteLevel] = useState(0);

  // Diagnostics
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [diagnostics, setDiagnostics] = useState({
    iceConnectionState: 'new',
    signalingState: 'stable',
    localTracks: 0,
    remoteTracks: 0,
    bytesReceived: 0,
    bytesSent: 0
  });

  // WebRTC and WebSocket refs
  const wsRef = useRef(null);
  const pcRef = useRef(null);
  const localStreamRef = useRef(null);
  const remoteAudioRef = useRef(null);

  // Audio analyzers
  const micAnalyzerRef = useRef(null);
  const remoteAnalyzerRef = useRef(null);
  const audioContextRef = useRef(null);
  const animationFrameRef = useRef(null);

  /**
   * Initialize audio analyzers for level visualization
   */
  const initializeAudioAnalyzers = useCallback(() => {
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
    }

    const audioContext = audioContextRef.current;

    // Microphone analyzer
    if (localStreamRef.current && !micAnalyzerRef.current) {
      const micSource = audioContext.createMediaStreamSource(localStreamRef.current);
      micAnalyzerRef.current = audioContext.createAnalyser();
      micAnalyzerRef.current.fftSize = 256;
      micSource.connect(micAnalyzerRef.current);
    }

    // Remote audio analyzer
    if (remoteAudioRef.current && remoteAudioRef.current.srcObject && !remoteAnalyzerRef.current) {
      const remoteSource = audioContext.createMediaElementSource(remoteAudioRef.current);
      remoteAnalyzerRef.current = audioContext.createAnalyser();
      remoteAnalyzerRef.current.fftSize = 256;
      remoteSource.connect(remoteAnalyzerRef.current);
      remoteAnalyzerRef.current.connect(audioContext.destination);
    }
  }, []);

  /**
   * Update audio levels for visualization
   */
  const updateAudioLevels = useCallback(() => {
    // Microphone level
    if (micAnalyzerRef.current && isSpeaking) {
      const dataArray = new Uint8Array(micAnalyzerRef.current.frequencyBinCount);
      micAnalyzerRef.current.getByteFrequencyData(dataArray);
      const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
      setMicLevel(Math.min(100, (average / 255) * 100));
    } else {
      setMicLevel(0);
    }

    // Remote audio level
    if (remoteAnalyzerRef.current && isListening) {
      const dataArray = new Uint8Array(remoteAnalyzerRef.current.frequencyBinCount);
      remoteAnalyzerRef.current.getByteFrequencyData(dataArray);
      const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
      setRemoteLevel(Math.min(100, (average / 255) * 100));
    } else {
      setRemoteLevel(0);
    }

    animationFrameRef.current = requestAnimationFrame(updateAudioLevels);
  }, [isSpeaking, isListening]);

  /**
   * Update WebRTC diagnostics
   */
  const updateDiagnostics = useCallback(async () => {
    if (!pcRef.current) return;

    try {
      const stats = await pcRef.current.getStats();
      let bytesReceived = 0;
      let bytesSent = 0;

      stats.forEach(report => {
        if (report.type === 'inbound-rtp' && report.mediaType === 'audio') {
          bytesReceived += report.bytesReceived || 0;
        }
        if (report.type === 'outbound-rtp' && report.mediaType === 'audio') {
          bytesSent += report.bytesSent || 0;
        }
      });

      setDiagnostics({
        iceConnectionState: pcRef.current.iceConnectionState,
        signalingState: pcRef.current.signalingState,
        localTracks: localStreamRef.current?.getTracks().length || 0,
        remoteTracks: remoteAudioRef.current?.srcObject?.getTracks().length || 0,
        bytesReceived,
        bytesSent
      });
    } catch (err) {
      logger.error('Error updating diagnostics:', err);
    }
  }, []);

  /**
   * Connect to camera audio
   */
  const connect = async () => {
    setIsConnecting(true);
    setError(null);
    setAudioPlaybackBlocked(false);

    try {
      // Request microphone permission
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      localStreamRef.current = stream;

      // Create WebRTC peer connection
      pcRef.current = new RTCPeerConnection({
        iceServers: [
          { urls: 'stun:stun.l.google.com:19302' },
          { urls: 'stun:stun1.l.google.com:19302' }
        ]
      });

      // Add local audio tracks to peer connection
      stream.getTracks().forEach(track => {
        pcRef.current.addTrack(track, stream);
      });

      // Handle remote audio tracks
      pcRef.current.ontrack = (event) => {
        logger.log('Received remote audio track');
        if (remoteAudioRef.current && event.streams[0]) {
          remoteAudioRef.current.srcObject = event.streams[0];
          remoteAudioRef.current.volume = volume;

          // Try to autoplay
          remoteAudioRef.current.play().then(() => {
            logger.log('Remote audio autoplay successful');
            setIsListening(true);
            setAudioPlaybackBlocked(false);
          }).catch(err => {
            logger.warn('Autoplay blocked, user interaction required:', err);
            setAudioPlaybackBlocked(true);
            setIsListening(false);
          });
        }
      };

      // Handle ICE connection state changes
      pcRef.current.oniceconnectionstatechange = () => {
        logger.log('ICE connection state:', pcRef.current.iceConnectionState);
        updateDiagnostics();

        if (pcRef.current.iceConnectionState === 'failed') {
          setError('Connection failed. Please try again.');
          disconnect();
        }
      };

      // Connect WebSocket
      const token = localStorage.getItem('access_token');
      const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/audio/ws/${cameraId}?token=${token}`;

      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = async () => {
        logger.log('WebSocket connected');

        try {
          // Create and send offer
          const offer = await pcRef.current.createOffer({
            offerToReceiveAudio: true
          });
          await pcRef.current.setLocalDescription(offer);

          wsRef.current.send(JSON.stringify({
            type: 'offer',
            sdp: offer.sdp
          }));

          setIsConnected(true);
          setIsConnecting(false);

          // In PTT mode, don't enable mic by default
          if (!pttMode) {
            setIsSpeaking(true);
          }

          // Initialize audio analyzers
          setTimeout(() => {
            initializeAudioAnalyzers();
            updateAudioLevels();
          }, 500);

          // Start diagnostics updates
          const diagnosticsInterval = setInterval(updateDiagnostics, 2000);
          pcRef.current.diagnosticsInterval = diagnosticsInterval;

        } catch (err) {
          logger.error('Error creating offer:', err);
          setError('Failed to establish connection');
          setIsConnecting(false);
          disconnect();
        }
      };

      wsRef.current.onmessage = async (event) => {
        try {
          const message = JSON.parse(event.data);

          if (message.type === 'answer') {
            logger.log('Received answer from server');
            await pcRef.current.setRemoteDescription({
              type: 'answer',
              sdp: message.sdp
            });
          } else if (message.type === 'ice-candidate' && message.candidate) {
            logger.log('Received ICE candidate');
            await pcRef.current.addIceCandidate(new RTCIceCandidate(message.candidate));
          }
        } catch (err) {
          logger.error('Error handling WebSocket message:', err);
        }
      };

      wsRef.current.onerror = (err) => {
        logger.error('WebSocket error:', err);
        setError('WebSocket connection failed');
        setIsConnecting(false);
        disconnect();
      };

      wsRef.current.onclose = () => {
        logger.log('WebSocket closed');
        if (isConnected) {
          setError('Connection lost');
        }
        setIsConnected(false);
        setIsConnecting(false);
      };

    } catch (err) {
      logger.error('Connection error:', err);

      if (err.name === 'NotAllowedError') {
        setError('Microphone permission denied. Please allow microphone access.');
      } else if (err.name === 'NotFoundError') {
        setError('No microphone found. Please connect a microphone.');
      } else {
        setError('Failed to access microphone: ' + err.message);
      }

      setIsConnecting(false);
    }
  };

  /**
   * Disconnect from camera audio
   */
  const disconnect = () => {
    logger.log('Disconnecting audio...');

    // Stop audio level updates
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    // Clear diagnostics interval
    if (pcRef.current?.diagnosticsInterval) {
      clearInterval(pcRef.current.diagnosticsInterval);
    }

    // Stop local stream
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach(track => {
        track.stop();
      });
      localStreamRef.current = null;
    }

    // Close WebRTC connection
    if (pcRef.current) {
      pcRef.current.close();
      pcRef.current = null;
    }

    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    // Reset audio analyzers
    micAnalyzerRef.current = null;
    remoteAnalyzerRef.current = null;

    setIsConnected(false);
    setIsConnecting(false);
    setIsSpeaking(false);
    setIsListening(false);
    setAudioPlaybackBlocked(false);
    setPttActive(false);
  };

  /**
   * Enable audio playback (for browser autoplay fix)
   */
  const enableAudioPlayback = () => {
    if (remoteAudioRef.current) {
      remoteAudioRef.current.play().then(() => {
        logger.log('Audio playback enabled by user');
        setIsListening(true);
        setAudioPlaybackBlocked(false);
      }).catch(err => {
        logger.error('Failed to enable audio playback:', err);
        setError('Failed to enable audio playback. Please try again.');
      });
    }
  };

  /**
   * Toggle microphone on/off
   */
  const toggleMicrophone = () => {
    if (localStreamRef.current) {
      const audioTrack = localStreamRef.current.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled;
        setIsSpeaking(audioTrack.enabled);
      }
    }
  };

  /**
   * Toggle speaker on/off
   */
  const toggleSpeaker = () => {
    if (remoteAudioRef.current) {
      remoteAudioRef.current.muted = !remoteAudioRef.current.muted;
      setIsListening(!remoteAudioRef.current.muted);
    }
  };

  /**
   * Handle volume change
   */
  const handleVolumeChange = (e) => {
    const newVolume = parseFloat(e.target.value);
    setVolume(newVolume);
    if (remoteAudioRef.current) {
      remoteAudioRef.current.volume = newVolume;
    }
  };

  /**
   * Handle PTT button press
   */
  const handlePTTPress = () => {
    if (!pttMode) return;

    setPttActive(true);

    // Enable microphone, mute speaker
    if (localStreamRef.current) {
      const audioTrack = localStreamRef.current.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = true;
        setIsSpeaking(true);
      }
    }

    if (remoteAudioRef.current) {
      remoteAudioRef.current.muted = true;
      setIsListening(false);
    }
  };

  /**
   * Handle PTT button release
   */
  const handlePTTRelease = () => {
    if (!pttMode) return;

    setPttActive(false);

    // Mute microphone, unmute speaker
    if (localStreamRef.current) {
      const audioTrack = localStreamRef.current.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = false;
        setIsSpeaking(false);
      }
    }

    if (remoteAudioRef.current) {
      remoteAudioRef.current.muted = false;
      setIsListening(true);
    }
  };

  /**
   * Toggle PTT mode
   */
  const togglePTTMode = () => {
    const newPttMode = !pttMode;
    setPttMode(newPttMode);

    if (newPttMode && isConnected) {
      // Entering PTT mode - mute mic, unmute speaker
      if (localStreamRef.current) {
        const audioTrack = localStreamRef.current.getAudioTracks()[0];
        if (audioTrack) {
          audioTrack.enabled = false;
          setIsSpeaking(false);
        }
      }
      if (remoteAudioRef.current) {
        remoteAudioRef.current.muted = false;
        setIsListening(true);
      }
    } else if (!newPttMode && isConnected) {
      // Exiting PTT mode - enable mic, keep speaker on
      if (localStreamRef.current) {
        const audioTrack = localStreamRef.current.getAudioTracks()[0];
        if (audioTrack) {
          audioTrack.enabled = true;
          setIsSpeaking(true);
        }
      }
    }
  };

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      disconnect();
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, []);

  return (
    <div className="two-way-audio">
      <div className="two-way-audio-header">
        <h3>Two-Way Audio</h3>
        <p className="two-way-audio-description">
          Communicate with your camera in real-time
        </p>
      </div>

      {error && (
        <div className="two-way-audio-error">
          <span className="error-icon">⚠️</span>
          <span className="error-message">{error}</span>
          <button
            className="error-dismiss"
            onClick={() => setError(null)}
            aria-label="Dismiss error"
          >
            ✕
          </button>
        </div>
      )}

      {audioPlaybackBlocked && (
        <div className="audio-playback-blocked">
          <span className="info-icon">ℹ️</span>
          <span className="info-message">
            Your browser blocked audio playback. Click below to enable audio.
          </span>
          <button
            className="audio-button audio-button-primary"
            onClick={enableAudioPlayback}
          >
            <span className="button-icon">🔊</span>
            <span className="button-text">Enable Audio</span>
          </button>
        </div>
      )}

      {!isConnected && !isConnecting && (
        <button
          className="audio-button audio-button-primary"
          onClick={connect}
        >
          <span className="button-icon">🎤</span>
          <span className="button-text">Connect Audio</span>
        </button>
      )}

      {isConnecting && (
        <div className="audio-connecting">
          <div className="spinner"></div>
          <span>Connecting...</span>
        </div>
      )}

      {isConnected && (
        <div className="audio-controls">
          <div className="audio-status">
            <span className="status-indicator"></span>
            <span className="status-text">Live</span>
            <button
              className="diagnostics-toggle"
              onClick={() => setShowDiagnostics(!showDiagnostics)}
              title="Toggle diagnostics"
            >
              {showDiagnostics ? '📊' : '📈'}
            </button>
          </div>

          {/* Audio Level Indicators */}
          <div className="audio-levels">
            <div className="audio-level-item">
              <span className="level-label">Microphone</span>
              <div className="level-bar-container">
                <div
                  className="level-bar level-bar-mic"
                  style={{ width: `${micLevel}%` }}
                ></div>
              </div>
            </div>
            <div className="audio-level-item">
              <span className="level-label">Camera Audio</span>
              <div className="level-bar-container">
                <div
                  className="level-bar level-bar-remote"
                  style={{ width: `${remoteLevel}%` }}
                ></div>
              </div>
            </div>
          </div>

          {/* Volume Control */}
          <div className="volume-control">
            <span className="volume-label">🔊 Volume</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={volume}
              onChange={handleVolumeChange}
              className="volume-slider"
            />
            <span className="volume-value">{Math.round(volume * 100)}%</span>
          </div>

          {/* PTT Mode Toggle */}
          <div className="ptt-mode-toggle">
            <label className="toggle-label">
              <input
                type="checkbox"
                checked={pttMode}
                onChange={togglePTTMode}
              />
              <span className="toggle-text">Push-to-Talk Mode</span>
            </label>
            <span className="toggle-description">
              {pttMode ? 'Hold button to speak' : 'Always-on microphone'}
            </span>
          </div>

          {/* Control Buttons */}
          {pttMode ? (
            <button
              className={`audio-button ptt-button ${pttActive ? 'ptt-active' : ''}`}
              onMouseDown={handlePTTPress}
              onMouseUp={handlePTTRelease}
              onMouseLeave={handlePTTRelease}
              onTouchStart={handlePTTPress}
              onTouchEnd={handlePTTRelease}
            >
              <span className="button-icon">{pttActive ? '🎤' : '🔇'}</span>
              <span className="button-text">
                {pttActive ? 'Speaking...' : 'Hold to Talk'}
              </span>
            </button>
          ) : (
            <div className="audio-button-group">
              <button
                className={`audio-button audio-control-button ${isSpeaking ? 'active' : 'inactive'}`}
                onClick={toggleMicrophone}
                title={isSpeaking ? 'Mute microphone' : 'Unmute microphone'}
              >
                <span className="button-icon">{isSpeaking ? '🎤' : '🔇'}</span>
                <span className="button-text">{isSpeaking ? 'Speaking' : 'Muted'}</span>
              </button>

              <button
                className={`audio-button audio-control-button ${isListening ? 'active' : 'inactive'}`}
                onClick={toggleSpeaker}
                title={isListening ? 'Mute speaker' : 'Unmute speaker'}
              >
                <span className="button-icon">{isListening ? '🔊' : '🔇'}</span>
                <span className="button-text">{isListening ? 'Listening' : 'Muted'}</span>
              </button>
            </div>
          )}

          {/* Diagnostics Panel */}
          {showDiagnostics && (
            <div className="diagnostics-panel">
              <h4>Connection Diagnostics</h4>
              <div className="diagnostics-grid">
                <div className="diagnostic-item">
                  <span className="diagnostic-label">ICE State:</span>
                  <span className="diagnostic-value">{diagnostics.iceConnectionState}</span>
                </div>
                <div className="diagnostic-item">
                  <span className="diagnostic-label">Signaling:</span>
                  <span className="diagnostic-value">{diagnostics.signalingState}</span>
                </div>
                <div className="diagnostic-item">
                  <span className="diagnostic-label">Local Tracks:</span>
                  <span className="diagnostic-value">{diagnostics.localTracks}</span>
                </div>
                <div className="diagnostic-item">
                  <span className="diagnostic-label">Remote Tracks:</span>
                  <span className="diagnostic-value">{diagnostics.remoteTracks}</span>
                </div>
                <div className="diagnostic-item">
                  <span className="diagnostic-label">Bytes Sent:</span>
                  <span className="diagnostic-value">{(diagnostics.bytesSent / 1024).toFixed(1)} KB</span>
                </div>
                <div className="diagnostic-item">
                  <span className="diagnostic-label">Bytes Received:</span>
                  <span className="diagnostic-value">{(diagnostics.bytesReceived / 1024).toFixed(1)} KB</span>
                </div>
              </div>
            </div>
          )}

          <button
            className="audio-button audio-button-danger"
            onClick={disconnect}
          >
            <span className="button-icon">⏹</span>
            <span className="button-text">Disconnect</span>
          </button>
        </div>
      )}

      {/* Hidden audio element for remote stream */}
      <audio ref={remoteAudioRef} style={{ display: 'none' }} />
    </div>
  );
};

export default TwoWayAudio;
