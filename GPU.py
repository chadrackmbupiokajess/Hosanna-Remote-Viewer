import wmi
import psutil
import sys # Import sys to print exception info

def get_gpu_info():
    gpu_data = {}

    # Récupérer informations générales GPU (nom, RAM, driver)
    try:
        w = wmi.WMI(namespace="root\\CIMV2")
        for gpu in w.Win32_VideoController():
            gpu_data["name"] = gpu.Name
            gpu_data["driver_version"] = gpu.DriverVersion
            gpu_data["ram_mb"] = int(gpu.AdapterRAM) // (1024 * 1024)
            gpu_data["ram_gb"] = round(gpu.AdapterRAM / (1024**3), 2)
            break
    except Exception as e: # Catch specific exception
        print(f"[*] DEBUG GPU: Erreur lors de la récupération des infos générales GPU: {e}", file=sys.stderr)
        gpu_data["name"] = "Unknown GPU"
        gpu_data["driver_version"] = "Unknown"
        gpu_data["ram_mb"] = 0
        gpu_data["ram_gb"] = 0

    # Récupérer utilisation GPU Intel (%)
    try:
        w_perf = wmi.WMI(namespace="root\\CIMV2")
        sensors = w_perf.Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine()

        gpu_usage = 0
        for s in sensors:
            # On prend uniquement le moteur 3D = vrai GPU load
            if "engtype_3D" in s.Name:
                gpu_usage += int(s.UtilizationPercentage)

        gpu_data["usage_percent"] = gpu_usage

    except Exception as e: # Catch specific exception
        print(f"[*] DEBUG GPU: Erreur lors de la récupération de l'utilisation GPU: {e}", file=sys.stderr)
        gpu_data["usage_percent"] = 0

    return gpu_data


# ------------ TEST ----------------
if __name__ == "__main__":
    info = get_gpu_info()
    print("Nom GPU :", info["name"])
    print("Driver :", info["driver_version"])
    print("RAM GPU :", info["ram_mb"], "MB /", info["ram_gb"], "GB")
    print("Utilisation GPU :", info["usage_percent"], "%")
