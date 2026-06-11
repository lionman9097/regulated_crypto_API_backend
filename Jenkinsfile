@Library('EHC-Jenkins-Shared-Library') _

standardDockerPipeline([
    // Slack notification configuration
    slackEnabled: true,
    networkCheck: [
        'https://google.com', 
        'https://github.com'
    ],

    // Production
    prod: [
        branch: 'prod',
        artifact: [
            imageName: 'regulated_crypto_api-backend',
            registryProject: 'robot-crypto',
            registryDomain: 'ehc-staging:5000',
            credDockerUser: 'dockerId',
            credDockerPass: 'dockerPass'
        ],
        buildArgs: [
            DATABASE_URL: 'DATABASE_URL',
            REDIS_URL: 'REDIS_URL',
            BINANCE_BASE_URL: 'BINANCE_BASE_URL',
            BINANCE_WS_BASE_URL: 'BINANCE_WS_BASE_URL',
            CORS_ALLOW_ORIGINS: 'CORS_ALLOW_ORIGINS',
            RATE_LIMIT_PER_MINUTE: 'RATE_LIMIT_PER_MINUTE',
            JWT_SECRET_KEY: 'JWT_SECRET_KEY',
            JWT_ALGORITHM: 'JWT_ALGORITHM',
            JWT_ACCESS_TOKEN_EXPIRE_MINUTES: 'JWT_ACCESS_TOKEN_EXPIRE_MINUTES',
            MARKET_WS_INTERVAL_SECONDS: 'MARKET_WS_INTERVAL_SECONDS',
            KPI_WS_INTERVAL_SECONDS: 'KPI_WS_INTERVAL_SECONDS',
            GLOBAL_EXPOSURE_THRESHOLD: 'GLOBAL_EXPOSURE_THRESHOLD',
            MAX_LEVERAGE: 'MAX_LEVERAGE',
            BINANCE_API_KEY: 'BINANCE_API_KEY',
            BINANCE_API_SECRET: 'BINANCE_API_SECRET'
        ],
        explicitCreds: [
            BINANCE_BASE_URL: 'https://demo-fapi.binance.com',
            BINANCE_WS_BASE_URL: 'wss://demo-fstream.binance.com',
            CORS_ALLOW_ORIGINS: 'http://localhost:3000,http://127.0.0.1:3000,http://172.10.10.227:3989'
        ],
        buildCreds: [
            [id: 'regulated_crypto_API-backend-redis-url-prod', name: 'REDIS_URL'],
            [id: 'regulated_crypto_API-backend-database-url-prod', name: 'DATABASE_URL'],
            [id: 'regulated_crypto_API-backend-rate-limit-per-minute-prod', name: 'RATE_LIMIT_PER_MINUTE'],
            [id: 'regulated_crypto_API-backend-jwt-secret-key-prod', name: 'JWT_SECRET_KEY'],
            [id: 'regulated_crypto_API-backend-jwt-algorithm-prod', name: 'JWT_ALGORITHM'],
            [id: 'regulated_crypto_API-backend-jwt-access-token-expire-minutes-prod', name: 'JWT_ACCESS_TOKEN_EXPIRE_MINUTES'],
            [id: 'regulated_crypto_API-backend-market-ws-interval-seconds-prod', name: 'MARKET_WS_INTERVAL_SECONDS'],
            [id: 'regulated_crypto_API-backend-kpi-ws-interval-seconds-prod', name: 'KPI_WS_INTERVAL_SECONDS'],
            [id: 'regulated_crypto_API-backend-global-exposure-threshold-prod', name: 'GLOBAL_EXPOSURE_THRESHOLD'],
            [id: 'regulated_crypto_API-backend-max-leverage-prod', name: 'MAX_LEVERAGE'],
            [id: 'regulated_crypto_API-backend-binance-api-key-prod', name: 'BINANCE_API_KEY'],
            [id: 'regulated_crypto_API-backend-binance-api-secret-prod', name: 'BINANCE_API_SECRET']
        ],
        deployment: [
            serverName: 'Production Server',
            containerName: 'regulated_crypto_api-backend-production',
            port: '3989',
            containerPort: '8000',
            network: 'regulated_crypto_api-backend-production-network',
            networkBindIP: '172.10.10.227',
            credServ: 'servProd',
            credSshKey: 'sshKey',
            sshPort: 2299
        ]
    ]
])