// Rolevo private beta — reviewable deployment plan (AZ-001).
//
// PLANNING ARTIFACT ONLY. No `az deployment what-if`, provisioning call, or
// Azure credential was used to author or validate this file; deploy only
// after the owner reviews parameters, runs what-if and accepts the quote in
// docs/AZURE_PLAN.md. Topology matches docs/DEPLOYMENT.md.

@description('Azure region for all resources; disclosed to the owner.')
param location string = 'eastus'

@description('Environment name: staging or beta.')
@allowed(['staging', 'beta'])
param environmentName string = 'staging'

@description('Immutable image digest to run, e.g. rolevo@sha256:….')
param imageDigest string

@description('Entra External ID issuer URL for the dedicated tenant.')
param oidcIssuer string

@description('OIDC confidential client id.')
param oidcClientId string

@description('Public HTTPS origin for the app.')
param publicAppUrl string

@description('Comma-separated Chrome extension IDs allowed to call the API.')
param chromeExtensionIds string

@secure()
@description('PostgreSQL administrator password; supply at deploy time, never in source.')
param postgresAdminPassword string

var prefix = 'rolevo-${environmentName}'
var tags = {
  app: 'rolevo'
  environment: environmentName
  managedBy: 'bicep'
}

// ---------- networking ----------
resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: '${prefix}-vnet'
  location: location
  tags: tags
  properties: {
    addressSpace: { addressPrefixes: ['10.30.0.0/16'] }
    subnets: [
      {
        name: 'appservice'
        properties: {
          addressPrefix: '10.30.1.0/24'
          delegations: [
            {
              name: 'webapp'
              properties: { serviceName: 'Microsoft.Web/serverFarms' }
            }
          ]
        }
      }
      {
        name: 'database'
        properties: {
          addressPrefix: '10.30.2.0/24'
          delegations: [
            {
              name: 'postgres'
              properties: { serviceName: 'Microsoft.DBforPostgreSQL/flexibleServers' }
            }
          ]
        }
      }
    ]
  }
}

resource dnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.postgres.database.azure.com'
  location: 'global'
  tags: tags
}

resource dnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: dnsZone
  name: '${prefix}-dnslink'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

// ---------- database ----------
resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2023-12-01-preview' = {
  name: '${prefix}-pg'
  location: location
  tags: tags
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '17'
    administratorLogin: 'copilot_migrator'
    administratorLoginPassword: postgresAdminPassword
    storage: { storageSizeGB: 32 }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    network: {
      delegatedSubnetResourceId: '${vnet.id}/subnets/database'
      privateDnsZoneArmResourceId: dnsZone.id
      publicNetworkAccess: 'Disabled'
    }
    highAvailability: { mode: 'Disabled' }
  }
}

// ---------- registry ----------
resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: replace('${prefix}acr', '-', '')
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

// ---------- key vault ----------
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: '${prefix}-kv'
  location: location
  tags: tags
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled' // tighten to private endpoints during AZ-003
  }
}

resource kek 'Microsoft.KeyVault/vaults/keys@2023-07-01' = {
  parent: keyVault
  name: 'credential-kek'
  properties: {
    kty: 'RSA'
    keySize: 2048
    keyOps: ['wrapKey', 'unwrapKey']
  }
}

// ---------- storage ----------
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: replace('${prefix}st', '-', '')
  location: location
  tags: tags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false // managed identity is the only data-plane auth
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

// Export artifacts share this private container under the `exports/` key
// prefix; container-level separation stays a recovery-plan decision.
resource documentsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'user-documents'
  properties: { publicAccess: 'None' }
}

// ---------- monitoring ----------
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${prefix}-insights'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    RetentionInDays: 30
    IngestionMode: 'ApplicationInsights'
  }
}

// ---------- app service ----------
resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${prefix}-plan'
  location: location
  tags: tags
  sku: {
    name: 'B1'
    tier: 'Basic'
    capacity: 1
  }
  kind: 'linux'
  properties: { reserved: true }
}

resource app 'Microsoft.Web/sites@2023-12-01' = {
  name: '${prefix}-app'
  location: location
  tags: tags
  kind: 'app,linux,container'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    virtualNetworkSubnetId: '${vnet.id}/subnets/appservice'
    siteConfig: {
      linuxFxVersion: 'DOCKER|${acr.properties.loginServer}/${imageDigest}'
      acrUseManagedIdentityCreds: true
      alwaysOn: true
      healthCheckPath: '/health/ready'
      minTlsVersion: '1.2'
      appSettings: [
        { name: 'WEBSITES_PORT', value: '8080' }
        { name: 'CHROME_EXTENSION_IDS', value: chromeExtensionIds }
        { name: 'APP_ENV', value: environmentName }
        { name: 'WEB_APP_ORIGIN', value: publicAppUrl }
        { name: 'LOCAL_MOCKS_ENABLED', value: 'false' }
        { name: 'CREDENTIAL_KEK_PROVIDER', value: 'key_vault' }
        { name: 'WEB_DIST_DIR', value: '/srv/web' }
        { name: 'OIDC_ISSUER', value: oidcIssuer }
        { name: 'OIDC_CLIENT_ID', value: oidcClientId }
        { name: 'OIDC_REDIRECT_URI', value: '${publicAppUrl}/auth/callback' }
        { name: 'DATABASE_URL', value: '@Microsoft.KeyVault(SecretUri=${keyVault.properties.vaultUri}secrets/db-runtime-url)' }
        { name: 'AUTH_DATABASE_URL', value: '@Microsoft.KeyVault(SecretUri=${keyVault.properties.vaultUri}secrets/db-auth-url)' }
        { name: 'WORKER_DATABASE_URL', value: '@Microsoft.KeyVault(SecretUri=${keyVault.properties.vaultUri}secrets/db-worker-url)' }
        { name: 'SCHEDULER_DATABASE_URL', value: '@Microsoft.KeyVault(SecretUri=${keyVault.properties.vaultUri}secrets/db-scheduler-url)' }
        { name: 'MIGRATION_DATABASE_URL', value: '@Microsoft.KeyVault(SecretUri=${keyVault.properties.vaultUri}secrets/db-migration-url)' }
        { name: 'OIDC_CLIENT_SECRET', value: '@Microsoft.KeyVault(SecretUri=${keyVault.properties.vaultUri}secrets/oidc-client-secret)' }
        { name: 'APP_HASH_KEY', value: '@Microsoft.KeyVault(SecretUri=${keyVault.properties.vaultUri}secrets/app-hash-key)' }
        { name: 'AUTH_TRANSACTION_ENCRYPTION_KEY', value: '@Microsoft.KeyVault(SecretUri=${keyVault.properties.vaultUri}secrets/auth-transaction-key)' }
        { name: 'BETA_ALLOWED_EMAILS', value: '@Microsoft.KeyVault(SecretUri=${keyVault.properties.vaultUri}secrets/beta-allowlist)' }
        { name: 'BLOB_ENDPOINT_URL', value: storage.properties.primaryEndpoints.blob }
        { name: 'KEY_VAULT_CREDENTIAL_KEK_ID', value: kek.properties.keyUriWithVersion }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
        { name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE', value: 'false' }
      ]
    }
  }
}

// ---------- RBAC: app managed identity ----------
var acrPullRole = '7f951dda-4ed3-4680-a7ca-43fe172d538d' // AcrPull
resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, app.id, acrPullRole)
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRole)
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

var cryptoUserRole = 'e147488a-f6f5-4113-8e2d-b22465e65bf6' // Key Vault Crypto User
resource kekAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kek.id, app.id, cryptoUserRole)
  scope: kek
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cryptoUserRole)
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

var blobDataContributorRole = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
resource blobAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, app.id, blobDataContributorRole)
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDataContributorRole)
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

var secretsUserRole = '4633458b-17de-408a-b874-0445c86b69e6' // Key Vault Secrets User
resource secretAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, app.id, secretsUserRole)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', secretsUserRole)
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output appName string = app.name
output registryLoginServer string = acr.properties.loginServer
output postgresFqdn string = postgres.properties.fullyQualifiedDomainName
output keyVaultUri string = keyVault.properties.vaultUri
