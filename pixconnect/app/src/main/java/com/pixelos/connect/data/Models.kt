package com.pixelos.connect.data

import androidx.room.*

@Entity
data class NetworkProfile(
    @PrimaryKey val name: String,
    val ssid: String,
    val password: String,
    val meshEnabled: Boolean,
    val firewallEnabled: Boolean,
    val dataLimitMb: Int
)

@Entity
data class DataUsageRecord(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val date: Long,
    val rxBytes: Long,
    val txBytes: Long,
    val ssid: String
)

@Dao
interface NetworkProfileDao {
    @Query("SELECT * FROM NetworkProfile")
    fun getAll(): List<NetworkProfile>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    fun insert(profile: NetworkProfile)

    @Delete
    fun delete(profile: NetworkProfile)
}

@Dao
interface DataUsageDao {
    @Query("SELECT * FROM DataUsageRecord ORDER BY date DESC")
    fun getAll(): List<DataUsageRecord>

    @Insert
    fun insert(record: DataUsageRecord)
}
