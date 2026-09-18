package net.abovebeyond.codieai.privileged;

interface IPrivilegedBridge {
    void destroy() = 16777114;
    String status() = 1;
    String listUserPackages() = 2;
    String packageInfo(String packageName) = 3;
    String forceStop(String packageName) = 4;
    String batteryDump() = 5;
    String memoryInfo(String packageName) = 6;
    String setAnimationScale(float scale) = 7;
    String setStayAwake(boolean enabled) = 8;
}
