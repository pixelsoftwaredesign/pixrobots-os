package com.pixelos.livestream.webrtc

import android.content.Context
import org.webrtc.*

object WebRTCClient {
    private var peerConnectionFactory: PeerConnectionFactory? = null
    private var peerConnection: PeerConnection? = null
    private var localVideoSource: VideoSource? = null
    private var localAudioSource: AudioSource? = null
    private var localVideoTrack: VideoTrack? = null
    private var localAudioTrack: AudioTrack? = null

    fun init(context: Context) {
        PeerConnectionFactory.initialize(PeerConnectionFactory.InitializationOptions.builder(context).createInitializationOptions())
        val factory = PeerConnectionFactory.builder().createPeerConnectionFactory()
        peerConnectionFactory = factory

        val audioConstraints = MediaConstraints().apply {
            mandatory.add(MediaConstraints.KeyValuePair("googEchoCancellation", "true"))
            mandatory.add(MediaConstraints.KeyValuePair("googNoiseSuppression", "true"))
        }
        localAudioSource = factory.createAudioSource(audioConstraints)
        localAudioTrack = factory.createAudioTrack("audio0", localAudioSource)

        val videoCapturer = createCameraCapturer(context)
        if (videoCapturer != null) {
            localVideoSource = factory.createVideoSource(videoCapturer.surfaceTextureHelper!!.isDisposed)
        }
    }

    private fun createCameraCapturer(context: Context): CameraVideoCapturer? {
        val enumerator = Camera2Enumerator(context)
        val deviceNames = enumerator.deviceNames
        for (name in deviceNames) {
            if (enumerator.isFrontFacing(name)) return enumerator.createCapturer(name, null)
        }
        for (name in deviceNames) {
            if (enumerator.isBackFacing(name)) return enumerator.createCapturer(name, null)
        }
        return null
    }

    fun getLocalVideoTrack(): VideoTrack? = localVideoTrack
    fun getLocalAudioTrack(): AudioTrack? = localAudioTrack

    fun createPeerConnection(observer: PeerConnection.Observer): PeerConnection? {
        val config = PeerConnection.RTCConfiguration(emptyList())
        config.sdpSemantics = PeerConnection.SdpSemantics.UNIFIED_PLAN
        return peerConnectionFactory?.createPeerConnection(config, observer)
    }

    fun dispose() {
        peerConnection?.dispose()
        peerConnectionFactory?.dispose()
    }
}
