using Microsoft.AspNetCore.Mvc;

namespace GuideApi.Controllers;

[ApiController]
[Route("info")]
public sealed class InfoController(IWebHostEnvironment environment) : ControllerBase
{
    [HttpGet]
    public IActionResult GetInfo()
    {
        return Ok(new
        {
            name = "azure-appservice-dotnet-guide",
            version = "1.0.0",
            dotnet = "8.0",
            framework = "ASP.NET Core",
            environment = environment.EnvironmentName
        });
    }
}
