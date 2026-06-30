package com.pixelos.sdk.network

import com.pixelos.sdk.models.*
import retrofit2.Response
import retrofit2.http.*

interface ApiService {
    @GET("api/status")
    suspend fun getServerStatus(): Response<ServerStatus>

    @GET("api/tasks")
    suspend fun getTasks(): Response<List<Task>>

    @POST("api/tasks")
    suspend fun createTask(@Body task: Map<String, Any>): Response<Task>

    @GET("api/sensors")
    suspend fun getSensors(): Response<List<Sensor>>

    @GET("api/robots")
    suspend fun getRobots(): Response<List<Robot>>

    @GET("api/wallet/balance")
    suspend fun getWalletBalance(): Response<WalletBalance>

    @GET("api/pixdao/proposals")
    suspend fun getProposals(): Response<List<Proposal>>

    @POST("api/pixdao/vote")
    suspend fun vote(@Body vote: VoteRequest): Response<VoteResponse>

    @POST("api/auth/login")
    suspend fun login(@Body credentials: Map<String, String>): Response<AuthResponse>
}
