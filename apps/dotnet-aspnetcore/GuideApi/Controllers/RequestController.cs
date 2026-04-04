using Microsoft.AspNetCore.Mvc;

namespace GuideApi.Controllers;

[ApiController]
[Route("api/requests")]
public sealed class RequestController(ILogger<RequestController> logger) : ControllerBase
{
    [HttpGet("log-levels")]
    public IActionResult LogLevels()
    {
        logger.LogTrace("Trace log generated from /api/requests/log-levels.");
        logger.LogDebug("Debug log generated from /api/requests/log-levels.");
        logger.LogInformation("Information log generated from /api/requests/log-levels.");
        logger.LogWarning("Warning log generated from /api/requests/log-levels.");
        logger.LogError("Error log generated from /api/requests/log-levels.");
        logger.LogCritical("Critical log generated from /api/requests/log-levels.");

        return Ok(new
        {
            message = "Generated logs at Trace, Debug, Information, Warning, Error, and Critical levels.",
            timestamp = DateTime.UtcNow
        });
    }
}
