# Managed Identity

Use App Service managed identity with `Azure.Identity` and `DefaultAzureCredential` to access Azure resources without storing credentials.

## Prerequisites

- App Service app deployed and running
- Permission to assign RBAC roles on target Azure resources
- `Azure.Identity` and relevant Azure SDK packages installed

## Main content

### 1) Enable system-assigned managed identity

```bash
az webapp identity assign \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --name "$WEB_APP_NAME" \
  --output json
```

Capture principal ID:

```bash
export WEB_APP_PRINCIPAL_ID=$(az webapp identity show \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --name "$WEB_APP_NAME" \
  --query "principalId" \
  --output tsv)
```

### 2) Grant RBAC on target resource

Example: Key Vault secrets reader role assignment.

```bash
az role assignment create \
  --assignee-object-id "$WEB_APP_PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Key Vault Secrets User" \
  --scope "/subscriptions/<subscription-id>/resourceGroups/<rg-name>/providers/Microsoft.KeyVault/vaults/<vault-name>" \
  --output json
```

### 3) Add Azure SDK packages

```xml
<ItemGroup>
  <PackageReference Include="Azure.Identity" Version="1.12.0" />
  <PackageReference Include="Azure.Security.KeyVault.Secrets" Version="4.6.0" />
  <PackageReference Include="Azure.Storage.Blobs" Version="12.21.1" />
</ItemGroup>
```

### 4) Use DefaultAzureCredential in code

```csharp
using Azure.Identity;
using Azure.Security.KeyVault.Secrets;

builder.Services.AddSingleton(_ =>
{
    var vaultUri = new Uri("https://<vault-name>.vault.azure.net/");
    return new SecretClient(vaultUri, new DefaultAzureCredential());
});
```

Read secret in endpoint:

```csharp
[ApiController]
[Route("api/secrets")]
public sealed class SecretsController : ControllerBase
{
    private readonly SecretClient _secretClient;
    public SecretsController(SecretClient secretClient) => _secretClient = secretClient;

    [HttpGet("sample")]
    public async Task<IActionResult> GetSampleSecret(CancellationToken cancellationToken)
    {
        var secret = await _secretClient.GetSecretAsync("sample-secret", cancellationToken: cancellationToken);
        return Ok(new { name = secret.Value.Name, length = secret.Value.Value.Length });
    }
}
```

### 5) Local development behavior

`DefaultAzureCredential` uses local identity chain during development (Azure CLI / VS sign-in) and managed identity in App Service automatically.

```csharp
var credential = new DefaultAzureCredential(new DefaultAzureCredentialOptions
{
    ExcludeInteractiveBrowserCredential = true
});
```

### 6) Code-free auth pattern for Azure clients

Many Azure SDK clients only need endpoint + credential:

```csharp
var blobServiceClient = new BlobServiceClient(new Uri("https://<storage-account>.blob.core.windows.net"), new DefaultAzureCredential());
```

### 7) Azure DevOps identity-aware validation snippet

```yaml
- task: AzureCLI@2
  displayName: Verify managed identity principal exists
  inputs:
    azureSubscription: $(azureSubscription)
    scriptType: bash
    scriptLocation: inlineScript
    inlineScript: |
      az webapp identity show \
        --resource-group $(resourceGroupName) \
        --name $(webAppName) \
        --output table
```

!!! tip "Least privilege first"
    Assign only the minimum role at the narrowest scope.
    Prefer resource-level scope over subscription-level assignments.

## Verification

```bash
curl --silent "https://$WEB_APP_NAME.azurewebsites.net/api/secrets/sample"
```

Expect successful response without any secret stored in source code or App Settings plain text.

## Troubleshooting

### 403 from target resource

- Confirm correct role assignment and scope.
- Wait for RBAC propagation (can take several minutes).
- Verify managed identity principal ID used in assignment is current.

### Works locally but fails in App Service

- Confirm system-assigned identity is enabled on deployed app.
- Confirm outbound networking and DNS allow resource access.
- Remove local-only credential assumptions from code.

### Unexpected credential in local development

Set explicit exclusions in `DefaultAzureCredentialOptions` to prevent credential chain surprises.

## See Also

- [Key Vault References](key-vault-reference.md)
- [Azure SQL](azure-sql.md)
- For platform details, see [Azure App Service Guide](https://yeongseon.github.io/azure-app-service-practical-guide/)
