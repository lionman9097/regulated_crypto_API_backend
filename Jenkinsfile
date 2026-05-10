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
            BINANCE_API_KEY: 'BINANCE_API_KEY',
            BINANCE_API_SECRET: 'BINANCE_API_SECRET'
        ],
        buildCreds: [
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