namespace GuideApi.Services;

public sealed class LifecycleHostedService(ILogger<LifecycleHostedService> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        logger.LogInformation("Lifecycle hosted service started.");

        try
        {
            await Task.Delay(Timeout.Infinite, stoppingToken);
        }
        catch (OperationCanceledException)
        {
            logger.LogInformation("Lifecycle hosted service received cancellation token.");
        }
    }
}
