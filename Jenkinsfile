pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    parameters {
        booleanParam(
            name: 'RUN_COMPOSE_SMOKE',
            defaultValue: true,
            description: 'Run Docker Compose runtime smoke tests.'
        )

        booleanParam(
            name: 'RUN_SECURITY_SCAN',
            defaultValue: false,
            description: 'Run local Trivy/Gitleaks scans on the Jenkins agent. Enable only after tools are installed.'
        )

        choice(
            name: 'DATA_PROFILE',
            choices: ['small', 'medium'],
            description: 'Synthetic data profile used by the data quality gate.'
        )

        choice(
            name: 'DEPLOY_TARGET',
            choices: ['local-only', 'ecr-disabled', 'terraform-disabled', 'eks-disabled'],
            description: 'Target release stage. Non-local targets are placeholders until later sprints.'
        )
    }

    environment {
        PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${env.PATH}"

        APP_ENV = 'local'

        FRONTEND_PORT = '3000'
        API_PORT = '8000'
        POSTGRES_PORT = '5432'

        POSTGRES_DB = 'retailops'
        POSTGRES_USER = 'retailops'
        POSTGRES_PASSWORD = 'retailops'

        DATABASE_URL = "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${POSTGRES_PORT}/${POSTGRES_DB}"

        API_IMAGE = "retailops-api:${BUILD_NUMBER}"
        FRONTEND_IMAGE = "retailops-frontend:${BUILD_NUMBER}"

        REPORTS_DIR = 'ci-cd/reports'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Agent Toolchain Diagnostics') {
            steps {
                sh '''
                    echo "PATH=$PATH"

                    echo "--- Git ---"
                    which git || true
                    git --version || true

                    echo "--- Make ---"
                    which make || true
                    make --version || true

                    echo "--- Python ---"
                    which python3 || true
                    python3 --version || true
                    python3 -m pip --version || true

                    echo "--- Node / npm ---"
                    which node || true
                    node --version || true
                    which npm || true
                    npm --version || true

                    echo "--- Docker ---"
                    which docker || true
                    docker --version || true
                    docker compose version || true
                '''
            }
        }

        stage('Build Context') {
            steps {
                sh '''
                    echo "Build number: ${BUILD_NUMBER}"
                    echo "Git commit: ${GIT_COMMIT:-unknown}"
                    echo "Branch: ${BRANCH_NAME:-unknown}"
                    echo "Deploy target: ${DEPLOY_TARGET}"
                    mkdir -p "${REPORTS_DIR}"
                '''
            }
        }

        stage('Install Dependencies') {
            steps {
                sh 'make install'
            }
        }

        stage('Data Quality Gate') {
            steps {
                sh 'make data-quality DATA_PROFILE="${DATA_PROFILE}"'
            }
        }

        stage('Local CI Gate') {
            steps {
                sh 'make ci-local'
            }
        }

        stage('Docker Build') {
            steps {
                sh '''
                    make docker-build \
                        API_IMAGE="${API_IMAGE}" \
                        FRONTEND_IMAGE="${FRONTEND_IMAGE}"
                '''
            }
        }

        stage('Docker Compose Smoke Test') {
            when {
                expression { return params.RUN_COMPOSE_SMOKE }
            }
            steps {
                sh 'make compose-ci'
            }
        }

        stage('Security Scan') {
            when {
                expression { return params.RUN_SECURITY_SCAN }
            }
            steps {
                sh '''
                    make security-scan \
                        API_IMAGE="${API_IMAGE}" \
                        FRONTEND_IMAGE="${FRONTEND_IMAGE}"
                '''
            }
        }

        stage('Future: Push to ECR') {
            when {
                expression { return params.DEPLOY_TARGET == 'ecr-disabled' }
            }
            steps {
                echo 'ECR publishing is intentionally disabled until Sprint 11/12.'
                echo 'Future scope: docker tag, docker push to Amazon ECR, image metadata evidence.'
            }
        }

        stage('Future: Terraform Plan / Apply') {
            when {
                expression { return params.DEPLOY_TARGET == 'terraform-disabled' }
            }
            steps {
                echo 'Terraform deployment is intentionally disabled until Terraform/AWS foundation exists.'
                echo 'Future scope: terraform fmt, validate, plan, approval, controlled apply.'
            }
        }

        stage('Future: Deploy to Kubernetes / EKS') {
            when {
                expression { return params.DEPLOY_TARGET == 'eks-disabled' }
            }
            steps {
                echo 'Kubernetes/EKS deployment is intentionally disabled until cluster and manifests exist.'
                echo 'Future scope: kubectl/helm deploy, rollout status, smoke test, rollback evidence.'
            }
        }

        stage('Release Evidence Summary') {
            steps {
                sh '''
                    mkdir -p "${REPORTS_DIR}"
                    {
                      echo "RetailOps Jenkins release evidence"
                      echo "=================================="
                      echo "Build number: ${BUILD_NUMBER}"
                      echo "Git commit: ${GIT_COMMIT:-unknown}"
                      echo "Branch: ${BRANCH_NAME:-unknown}"
                      echo "Deploy target: ${DEPLOY_TARGET}"
                      echo "API image: ${API_IMAGE}"
                      echo "Frontend image: ${FRONTEND_IMAGE}"
                      echo "Compose smoke enabled: ${RUN_COMPOSE_SMOKE}"
                      echo "Security scan enabled: ${RUN_SECURITY_SCAN}"
                      echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
                    } > "${REPORTS_DIR}/jenkins-release-evidence.txt"
                '''
            }
        }
    }

    post {
        always {
            sh 'docker compose down -v --remove-orphans || true'

            archiveArtifacts(
                artifacts: 'ci-cd/reports/**',
                allowEmptyArchive: true,
                fingerprint: true
            )
        }

        success {
            echo 'RetailOps Jenkins release-confidence pipeline passed.'
        }

        failure {
            echo 'RetailOps Jenkins release-confidence pipeline failed. Check archived evidence and logs.'
        }
    }
}
