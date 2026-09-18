package net.abovebeyond.codieai.privileged

import android.content.ComponentName
import android.content.Context
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.os.IBinder
import rikka.shizuku.Shizuku
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

object ShizukuBridge {
    const val REQUEST_CODE = 7421

    @Volatile
    private var remote: IPrivilegedBridge? = null

    private val pendingLatch = AtomicReference<CountDownLatch?>(null)

    private val connection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
            remote = IPrivilegedBridge.Stub.asInterface(service)
            pendingLatch.getAndSet(null)?.countDown()
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            remote = null
            pendingLatch.getAndSet(null)?.countDown()
        }
    }

    fun status(): String {
        return try {
            if (!Shizuku.pingBinder()) {
                "Shizuku is not running or its binder is unavailable."
            } else if (Shizuku.isPreV11()) {
                "This Shizuku version is too old."
            } else if (Shizuku.checkSelfPermission() != PackageManager.PERMISSION_GRANTED) {
                "Shizuku is running but Codie AI permission has not been granted."
            } else {
                val uid = runCatching { Shizuku.getUid() }.getOrNull()
                val attached = remote?.asBinder()?.isBinderAlive == true
                "Shizuku ready; server_uid=" + (uid ?: "unknown") +
                    "; privileged_service_bound=" + attached
            }
        } catch (error: Throwable) {
            "Shizuku unavailable: " + (error.message ?: error.javaClass.simpleName)
        }
    }

    fun requestPermission(): String {
        return try {
            if (!Shizuku.pingBinder()) {
                "Install/start Shizuku first, then return to Codie AI."
            } else if (Shizuku.isPreV11()) {
                "Shizuku API v11 or newer is required."
            } else if (Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED) {
                "Shizuku permission is already granted."
            } else if (Shizuku.shouldShowRequestPermissionRationale()) {
                "Shizuku permission was denied. Re-enable Codie AI in Shizuku."
            } else {
                Shizuku.requestPermission(REQUEST_CODE)
                "Shizuku permission request opened."
            }
        } catch (error: Throwable) {
            "Could not request Shizuku permission: " +
                (error.message ?: error.javaClass.simpleName)
        }
    }

    fun privilegedStatus(context: Context): Result<String> =
        call(context) { it.status() }

    fun listUserPackages(context: Context): Result<String> =
        call(context) { it.listUserPackages() }

    fun packageInfo(context: Context, packageName: String): Result<String> =
        call(context) { it.packageInfo(packageName) }

    fun forceStop(context: Context, packageName: String): Result<String> =
        call(context) { it.forceStop(packageName) }

    fun batteryDump(context: Context): Result<String> =
        call(context) { it.batteryDump() }

    fun memoryInfo(context: Context, packageName: String): Result<String> =
        call(context) { it.memoryInfo(packageName) }

    fun setAnimationScale(context: Context, scale: Float): Result<String> =
        call(context) { it.setAnimationScale(scale) }

    fun setStayAwake(context: Context, enabled: Boolean): Result<String> =
        call(context) { it.setStayAwake(enabled) }

    private fun call(
        context: Context,
        block: (IPrivilegedBridge) -> String
    ): Result<String> = runCatching {
        val service = ensureService(context)
        block(service).take(32_000)
    }

    private fun ensureService(context: Context): IPrivilegedBridge {
        val existing = remote
        if (existing?.asBinder()?.isBinderAlive == true) return existing

        require(Shizuku.pingBinder()) {
            "Shizuku is not running. Start Shizuku before using privileged tools."
        }
        require(!Shizuku.isPreV11()) {
            "Shizuku API v11 or newer is required."
        }
        require(
            Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED
        ) {
            "Shizuku permission is required. Use the Shizuku button in Codie AI first."
        }

        val latch = CountDownLatch(1)
        pendingLatch.set(latch)

        val args = Shizuku.UserServiceArgs(
            ComponentName(context.packageName, PrivilegedUserService::class.java.name)
        )
            .processNameSuffix("codie_privileged")
            .tag("codie_ai_privileged_v1")
            .version(1)
            .daemon(false)

        Shizuku.bindUserService(args, connection)

        if (!latch.await(8, TimeUnit.SECONDS)) {
            pendingLatch.compareAndSet(latch, null)
            throw IllegalStateException("Timed out while binding privileged Shizuku service")
        }

        return remote?.takeIf { it.asBinder().isBinderAlive }
            ?: throw IllegalStateException("Shizuku privileged service did not connect")
    }
}
