namespace MinecraftSkinRunPod;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();

        try
        {
            Application.Run(new MainForm());
        }
        catch (Exception ex)
        {
            var logPath = WriteCrashLog(ex);

            MessageBox.Show(
                "Minecraft Skin Generator crashed.\n\n" +
                ex.GetType().FullName + ": " + ex.Message +
                "\n\nA detailed crash log was saved to:\n" + logPath,
                "Minecraft Skin Generator - Crash",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    private static string WriteCrashLog(Exception exception)
    {
        try
        {
            var directory = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "MinecraftSkinGenerator");

            Directory.CreateDirectory(directory);

            var path = Path.Combine(directory, "crash.log");

            File.WriteAllText(
                path,
                $"Time: {DateTimeOffset.Now:O}{Environment.NewLine}" +
                $"OS: {Environment.OSVersion}{Environment.NewLine}" +
                $".NET: {Environment.Version}{Environment.NewLine}" +
                $"64-bit process: {Environment.Is64BitProcess}{Environment.NewLine}" +
                $"{Environment.NewLine}{exception}");

            return path;
        }
        catch
        {
            return "(could not write crash.log)";
        }
    }
}
