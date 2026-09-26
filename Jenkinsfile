// Local validation only. Protected GitHub Required CI owns the broader security,
// registry, Terraform and Kubernetes gates; this pipeline does not deploy.
pipeline {
    agent any
    options {
        timestamps()
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
        timeout(time: 45, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }
    parameters {
        choice(name: 'DATA_PROFILE', choices: ['small', 'medium'],
               description: 'Synthetic data profile for local validation.')
    }
    environment {
        PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${env.PATH}"
        APP_ENV = 'local'
        REPORTS_DIR = 'ci-cd/reports'
        // Unit tests mock DB access; real runtime uses a private disposable DB.
        DATABASE_URL = 'postgresql://retailops:disposable-ci-only@127.0.0.1:1/retailops'
    }
    stages {
        stage('Checkout') {
            steps {
                deleteDir()
                checkout scm
                script {
                    // Explicit checkout does not always export Git plugin variables.
                    env.GIT_COMMIT = sh(script: 'git rev-parse HEAD', returnStdout: true).trim()
                }
            }
        }
        stage('Agent Toolchain') {
            steps {
                sh '''
                    set -eu
                    git --version
                    make --version
                    python3.11 --version
                    node --version
                    npm --version
                    docker --version
                    docker compose version
                    git rev-parse HEAD
                '''
            }
        }
        stage('Install Dependencies') {
            steps { sh 'make install' }
        }
        stage('Data Quality Gate') {
            steps { sh 'make data-quality DATA_PROFILE="${DATA_PROFILE:-small}"' }
        }
        stage('Local CI Gate') {
            steps { sh 'make ci-local DATA_PROFILE="${DATA_PROFILE:-small}"' }
        }
        stage('Isolated Build, Runtime and Alert Drill') {
            steps { sh 'make compose-ci' }
        }
    }
    post {
        always {
            script {
                sh 'mkdir -p ci-cd/reports'
                writeFile file: 'ci-cd/reports/jenkins-release-evidence.txt', text: """scope=local-validation
build_number=${env.BUILD_NUMBER}
source_commit=${env.GIT_COMMIT}
result=${currentBuild.currentResult}
data_profile=${params.DATA_PROFILE ?: 'small'}
compose_and_alert_drill=mandatory
security_gate=separate-protected-github-required-ci
"""
            }
            // Compose runner cleans only its own project, even after failure.
            archiveArtifacts(
                artifacts: 'ci-cd/reports/jenkins-release-evidence.txt,ci-cd/reports/api/coverage.xml,ci-cd/reports/data/*report.json,ci-cd/reports/data/generated/*/*report.json,ci-cd/reports/docker/isolated-runtime.json,ci-cd/reports/observability/incident-drill.json',
                allowEmptyArchive: false,
                fingerprint: true
            )
        }
    }
}
