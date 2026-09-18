package net.abovebeyond.codieai.privileged;

interface IPrivilegedBridge {
    void destroy() = 16777114;
    String status();
    String listUserPackages();
    String packageInfo(String packageName);
    String forceStop(String packageName);
    String batteryDump();
    String memoryInfo(String packageName);
    String setAnimationScale(float scale);
    String setStayAwake(boolean enabled);
}
