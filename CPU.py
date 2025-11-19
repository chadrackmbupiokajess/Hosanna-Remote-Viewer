import wmi
import psutil
import platform

def get_cpu_info():
    cpu_data = {}
    try:
        w = wmi.WMI()
        for cpu in w.Win32_Processor():
            cpu_data["name"] = cpu.Name            # Exemple : Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz
            cpu_data["cores"] = cpu.NumberOfCores
            cpu_data["threads"] = cpu.NumberOfLogicalProcessors
            cpu_data["usage_percent"] = psutil.cpu_percent(interval=1)
            break
    except:
        cpu_data["name"] = platform.processor()
        cpu_data["cores"] = psutil.cpu_count(logical=False)
        cpu_data["threads"] = psutil.cpu_count(logical=True)
        cpu_data["usage_percent"] = psutil.cpu_percent(interval=1)

    return cpu_data

def get_ram_info():
    ram = psutil.virtual_memory()
    ram_data = {
        "total_gb": ram.total // (1024**3),
        "available_gb": ram.available // (1024**3),
        "usage_percent": ram.percent
    }
    return ram_data

def get_gpu_info():
    gpu_data = {}
    try:
        w = wmi.WMI(namespace="root\\CIMV2")
        for gpu in w.Win32_VideoController():
            gpu_data["name"] = gpu.Name
            gpu_data["driver_version"] = gpu.DriverVersion
            gpu_data["ram_mb"] = int(gpu.AdapterRAM) // (1024 * 1024)
            break
    except:
        gpu_data["name"] = "Unknown GPU"
        gpu_data["driver_version"] = "Unknown"
        gpu_data["ram_mb"] = 0

    try:
        w_perf = wmi.WMI(namespace="root\\CIMV2")
        sensors = w_perf.Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine()
        gpu_usage = 0
        for s in sensors:
            if "engtype_3D" in s.Name:
                gpu_usage += int(s.UtilizationPercentage)
        gpu_data["usage_percent"] = gpu_usage
    except:
        gpu_data["usage_percent"] = 0

    return gpu_data

# ------------ TEST ----------------
if __name__ == "__main__":
    cpu_info = get_cpu_info()
    ram_info = get_ram_info()
    gpu_info = get_gpu_info()

    print("=== CPU ===")
    print("Nom :", cpu_info["name"])
    print("Cores :", cpu_info["cores"])
    print("Threads :", cpu_info["threads"])
    print("Utilisation CPU :", cpu_info["usage_percent"], "%\n")

    print("=== RAM ===")
    print("Total :", ram_info["total_gb"], "GB")
    print("Disponible :", ram_info["available_gb"], "GB")
    print("Utilisation RAM :", ram_info["usage_percent"], "%\n")

    print("=== GPU ===")
    print("Nom :", gpu_info["name"])
    print("Driver :", gpu_info["driver_version"])
    print("RAM :", gpu_info["ram_mb"], "MB")
    print("Utilisation GPU :", gpu_info["usage_percent"], "%")
