package net.abovebeyond.codieai.privileged;

import android.os.Process;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.Locale;
import java.util.concurrent.TimeUnit;
import java.util.regex.Pattern;

public final class PrivilegedUserService extends IPrivilegedBridge.Stub {
    private static final Pattern PACKAGE =
            Pattern.compile("[A-Za-z0-9_]+(?:\\.[A-Za-z0-9_]+)+");
    private static final int MAX_OUTPUT = 32000;

    public PrivilegedUserService() {
    }

    @Override
    public void destroy() {
        System.exit(0);
    }

    @Override
    public String status() {
        return "privileged_bridge uid=" + Process.myUid() +
                " pid=" + Process.myPid();
    }

    @Override
    public String listUserPackages() {
        return runLimited(
                new String[]{"/system/bin/cmd", "package", "list", "packages", "-3"}
        );
    }

    @Override
    public String packageInfo(String packageName) {
        String pkg = validPackage(packageName);
        String path = runLimited(
                new String[]{"/system/bin/cmd", "package", "path", pkg}
        );
        String dump = runLimited(
                new String[]{"/system/bin/dumpsys", "package", pkg}
        );
        return (path + "\n" + dump).trim();
    }

    @Override
    public String forceStop(String packageName) {
        String pkg = validPackage(packageName);
        String output = runLimited(
                new String[]{"/system/bin/am", "force-stop", pkg}
        );
        return "Force-stopped " + pkg +
                (output.isBlank() ? "" : "\n" + output);
    }

    @Override
    public String batteryDump() {
        return runLimited(new String[]{"/system/bin/dumpsys", "battery"});
    }

    @Override
    public String memoryInfo(String packageName) {
        String pkg = validPackage(packageName);
        return runLimited(
                new String[]{"/system/bin/dumpsys", "meminfo", pkg}
        );
    }

    @Override
    public String setAnimationScale(float scale) {
        if (!Float.isFinite(scale) || scale < 0f || scale > 10f) {
            throw new IllegalArgumentException("Animation scale must be from 0 to 10");
        }

        String value = String.format(Locale.US, "%.2f", scale);
        runLimited(new String[]{
                "/system/bin/settings", "put", "global",
                "window_animation_scale", value
        });
        runLimited(new String[]{
                "/system/bin/settings", "put", "global",
                "transition_animation_scale", value
        });
        runLimited(new String[]{
                "/system/bin/settings", "put", "global",
                "animator_duration_scale", value
        });
        return "Animation scales set to " + value;
    }

    @Override
    public String setStayAwake(boolean enabled) {
        String value = enabled ? "7" : "0";
        runLimited(new String[]{
                "/system/bin/settings", "put", "global",
                "stay_on_while_plugged_in", value
        });
        return enabled
                ? "Stay-awake while charging enabled"
                : "Stay-awake while charging disabled";
    }

    private static String validPackage(String raw) {
        String pkg = raw == null ? "" : raw.trim();
        if (!PACKAGE.matcher(pkg).matches()) {
            throw new IllegalArgumentException("Invalid Android package name");
        }
        return pkg;
    }

    private static String runLimited(String[] command) {
        ProcessBuilder builder = new ProcessBuilder(command);
        builder.redirectErrorStream(true);

        try {
            java.lang.Process process = builder.start();
            StringBuilder output = new StringBuilder();

            Thread reader = new Thread(() -> {
                try (BufferedReader buffered = new BufferedReader(
                        new InputStreamReader(process.getInputStream()))) {
                    String line;
                    while ((line = buffered.readLine()) != null) {
                        synchronized (output) {
                            if (output.length() < MAX_OUTPUT) {
                                if (output.length() > 0) output.append('\n');
                                int remaining = MAX_OUTPUT - output.length();
                                output.append(
                                        line,
                                        0,
                                        Math.min(line.length(), remaining)
                                );
                            }
                        }
                    }
                } catch (Throwable ignored) {
                }
            }, "codie-privileged-reader");
            reader.start();

            boolean finished = process.waitFor(8, TimeUnit.SECONDS);
            if (!finished) {
                process.destroyForcibly();
                throw new IllegalStateException("Privileged operation timed out");
            }

            reader.join(1000);
            int exit = process.exitValue();
            String text;
            synchronized (output) {
                text = output.toString();
            }

            if (exit != 0) {
                throw new IllegalStateException(
                        "Privileged operation failed with exit " + exit +
                                (text.isBlank() ? "" : ": " + text)
                );
            }
            return text;
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Privileged operation interrupted", error);
        } catch (Exception error) {
            if (error instanceof IllegalStateException) {
                throw (IllegalStateException) error;
            }
            throw new IllegalStateException(
                    error.getMessage() == null
                            ? error.getClass().getSimpleName()
                            : error.getMessage(),
                    error
            );
        }
    }
}
