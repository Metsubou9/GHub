using System;
using LibreHardwareMonitor.Hardware;

// GHub CPU temp helper: печатает "12.3" или "none".
// cputemp.exe --diag : диагностика (админ? сервис драйвера? сырые сенсоры?)
public static class CpuTemp
{
    public static void Main(string[] args)
    {
        if (args.Length > 0 && args[0] == "--diag") { Diag(); return; }
        var comp = new Computer { IsCpuEnabled = true };
        try
        {
            comp.Open();
            double? pkg = null;
            double max = double.NaN;
            foreach (var hw in comp.Hardware)
            {
                if (hw.HardwareType != HardwareType.Cpu) continue;
                hw.Update();
                foreach (var s in hw.Sensors)
                {
                    if (s.SensorType != SensorType.Temperature) continue;
                    var v = s.Value;
                    if (!v.HasValue || v.Value <= 0) continue; // 0 = драйвер не встал, данных нет
                    if (s.Name == "CPU Package") pkg = v.Value;
                    if (double.IsNaN(max) || v.Value > max) max = v.Value;
                }
            }
            double? res = pkg ?? (double.IsNaN(max) ? (double?)null : max);
            Console.WriteLine(res.HasValue
                ? res.Value.ToString("F1", System.Globalization.CultureInfo.InvariantCulture)
                : "none");
        }
        catch (Exception e)
        {
            Console.WriteLine("error:" + e.Message);
        }
        finally
        {
            try { comp.Close(); } catch { }
        }
    }

    private static void Diag()
    {
        bool admin = false;
        try
        {
            var id = System.Security.Principal.WindowsIdentity.GetCurrent();
            var pr = new System.Security.Principal.WindowsPrincipal(id);
            admin = pr.IsInRole(System.Security.Principal.WindowsBuiltInRole.Administrator);
        }
        catch { }
        Console.WriteLine("admin=" + admin);
        try
        {
            foreach (var s in System.ServiceProcess.ServiceController.GetServices())
            {
                string n = (s.ServiceName + " " + s.DisplayName).ToLowerInvariant();
                if (n.Contains("ring0") || n.Contains("librehardware") || n.Contains("pawn"))
                    Console.WriteLine("service: " + s.ServiceName + " status=" + s.Status);
            }
        }
        catch (Exception e) { Console.WriteLine("services_error=" + e.Message); }
        var comp = new Computer { IsCpuEnabled = true };
        try
        {
            comp.Open();
            foreach (var hw in comp.Hardware)
            {
                if (hw.HardwareType != HardwareType.Cpu) continue;
                Console.WriteLine("cpu=" + hw.Name);
                hw.Update();
                foreach (var s in hw.Sensors)
                {
                    if (s.SensorType != SensorType.Temperature) continue;
                    Console.WriteLine("sensor [" + s.Name + "] = " +
                        (s.Value.HasValue ? s.Value.Value.ToString("F1") : "null"));
                }
            }
        }
        catch (Exception e) { Console.WriteLine("open_error=" + e.Message); }
        finally { try { comp.Close(); } catch { } }
    }
}
