package com.pixelos.connect.manager

import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter

object BluetoothManager {
    private var bluetoothAdapter: BluetoothAdapter? = null
    private var discoveredDevices = mutableListOf<BluetoothDevice>()
    private var receiver: BroadcastReceiver? = null

    data class BleDevice(val name: String, val address: String, val type: String)

    fun init(context: Context) {
        bluetoothAdapter = BluetoothAdapter.getDefaultAdapter()
    }

    fun isEnabled(): Boolean = bluetoothAdapter?.isEnabled ?: false

    fun toggle(enable: Boolean) {
        if (enable) bluetoothAdapter?.enable() else bluetoothAdapter?.disable()
    }

    fun startDiscovery(context: Context): List<BleDevice> {
        discoveredDevices.clear()
        receiver = object : BroadcastReceiver() {
            override fun onReceive(ctx: Context, intent: Intent) {
                when (intent.action) {
                    BluetoothDevice.ACTION_FOUND -> {
                        val device = intent.getParcelableExtra<BluetoothDevice>(BluetoothDevice.EXTRA_DEVICE)
                        device?.let { if (!discoveredDevices.any { d -> d.address == it.address }) discoveredDevices.add(it) }
                    }
                }
            }
        }
        context.registerReceiver(receiver, IntentFilter(BluetoothDevice.ACTION_FOUND))
        bluetoothAdapter?.startDiscovery()
        return emptyList()
    }

    fun getPairedDevices(): List<BleDevice> {
        return bluetoothAdapter?.bondedDevices?.map {
            BleDevice(name = it.name ?: "Inconnu", address = it.address, type = classifyDevice(it))
        }?.toList() ?: emptyList()
    }

    private fun classifyDevice(device: BluetoothDevice): String {
        return when (device.bluetoothClass?.majorDeviceClass) {
            0x0100 -> "Ordinateur"
            0x0400 -> "Audio"
            0x0500 -> "Téléphone"
            0x1F00 -> "Capteur BLE"
            else -> "Appareil"
        }
    }

    fun stopDiscovery(context: Context) {
        receiver?.let { context.unregisterReceiver(it) }
        bluetoothAdapter?.cancelDiscovery()
    }

    fun connect(address: String) {
        val device = bluetoothAdapter?.getRemoteDevice(address)
        // device?.createBond() pour appairer
    }
}
