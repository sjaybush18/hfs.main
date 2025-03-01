import ota_update.updater as ota #import ota_updater# ota# OTAUpdater
import config
try:
    import device_sensor as device

    version = ota.OTAUpdater(config.GITHUB_URL, github_src_dir=config.GITHUB_SRC_DIR, dev_version_url=config.DEV_VERSION_FILE, update_sub_dir=config.UPDATE_SUB_DIR, main_dir=config.GITHUB_BRANCH)
    device.CURRENT_VERSION = int(float(version.get_version(version.modulepath(version.main_dir))))
    del(version)
except Exception as error:
    print(error)
        
def update():
    # connect to interweb
    import network
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print('[INFO] Connecting to network...') 
        sta_if.active(True)
        sta_if.connect(config.LAN_SSID, config.LAN_PASSWORD)
        while not sta_if.isconnected():
            pass
    print('[INFO] Connected to', config.LAN_SSID)
    print('[INFO] Network config {}'.format(sta_if.ifconfig()))
    # Check for updates
    print("[INFO] Checking for updates...")
    try: 
        # monitor memory
        import time, machine, gc
        time.sleep(1)
        print('[INFO] Memory free {}'.format(gc.mem_free()))
        # download and install an update if availible
        ota_updater = ota.OTAUpdater(config.GITHUB_URL, github_src_dir=config.GITHUB_SRC_DIR, dev_version_url=config.DEV_VERSION_FILE, update_sub_dir=config.UPDATE_SUB_DIR, main_dir=config.GITHUB_BRANCH)
        update = ota_updater.dev_install_update_if_available()
        CURRENT_VERSION = ota_updater.get_version(ota_updater.modulepath(ota_updater.main_dir))
        del(ota_updater)
        if (update):
            print("[INFO] Upgrade complete, reseting...")
            machine.reset()
    except Exception as e:
        print("WARNING: Update failed ({})".format(e))
    sta_if.disconnect()
    sta_if.active(False)