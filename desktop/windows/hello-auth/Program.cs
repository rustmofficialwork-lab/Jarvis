using System.Text.Json;
using Windows.Security.Credentials.UI;

internal static class Program
{
    [STAThread]
    private static async Task<int> Main(string[] args)
    {
        if (args.Length != 1 || !long.TryParse(args[0], out var rawHandle) || rawHandle <= 0)
        {
            WriteResult(false, "invalid_window", "JARVIS could not identify its verification window.");
            return 2;
        }

        try
        {
            var result = await UserConsentVerifierInterop.RequestVerificationForWindowAsync(
                new IntPtr(rawHandle),
                "Verify your identity to continue in JARVIS.");

            var verified = result == UserConsentVerificationResult.Verified;
            var code = result.ToString();
            WriteResult(verified, code, verified
                ? "Windows verified the signed-in user."
                : "Windows verification was not completed.");
            return verified ? 0 : 1;
        }
        catch (Exception)
        {
            WriteResult(false, "unavailable", "Windows Hello verification is unavailable on this device.");
            return 3;
        }
    }

    private static void WriteResult(bool verified, string code, string message)
    {
        Console.WriteLine(JsonSerializer.Serialize(new { verified, code, message }));
    }
}
