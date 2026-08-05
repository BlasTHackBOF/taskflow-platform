// TaskFlow CI/CD. Branch builds prove the code (lint, test, build,
// scan); main builds additionally ship it (push, deploy, smoke test) —
// the same split architecture.md promised. Credentials come only from
// the Jenkins credential store (ADR-0011): 'ghcr-push' (username +
// write:packages token) and 'k3s-kubeconfig' (secret file, private-IP
// server address). Nothing secret appears below.

pipeline {
  agent any

  options {
    // A hung build must not hold the 2 GiB CI node hostage.
    timeout(time: 30, unit: 'MINUTES')
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '20'))
    timestamps()
  }

  environment {
    IMAGE_REPO = 'ghcr.io/blasthackbof/taskflow-app'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        script {
          // One SHA flows through the whole pipeline: image tag, helm
          // value, smoke-test assertion. Rollback depends on it.
          env.GIT_SHA = sh(script: 'git rev-parse --short=12 HEAD', returnStdout: true).trim()
        }
      }
    }

    // Lint and test run in the prebuilt CI agent image (built by the
    // Ansible jenkins role from docker/ci/Dockerfile): the pinned
    // production python base with the dev toolchain preinstalled, and a
    // real uid-1000 user so pip has a writable HOME. The pip line syncs
    // the delta against this commit's pins — a no-op when nothing
    // changed, correct when a branch bumps a version.
    stage('Lint') {
      agent { docker { image 'taskflow-ci:py3.12.12-ci1'; reuseNode true } }
      steps {
        sh 'pip install --user --quiet -r app/requirements-dev.txt && ruff check app'
      }
    }

    stage('Test') {
      agent { docker { image 'taskflow-ci:py3.12.12-ci1'; reuseNode true } }
      steps {
        sh '''
          pip install --user --quiet -r app/requirements-dev.txt
          cd app
          mkdir -p reports
          python -m pytest --junitxml=reports/junit.xml \
                           --cov=taskflow --cov-report=xml:reports/coverage.xml
        '''
      }
      post {
        always {
          junit 'app/reports/junit.xml'
          archiveArtifacts artifacts: 'app/reports/coverage.xml', allowEmptyArchive: true
        }
      }
    }

    stage('Build image') {
      steps {
        sh '''
          docker build -f docker/Dockerfile \
            -t "$IMAGE_REPO:$GIT_SHA" \
            --build-arg GIT_SHA="$GIT_SHA" --build-arg APP_VERSION="$GIT_SHA" \
            --label org.opencontainers.image.source=https://github.com/BlasTHackBOF/taskflow-platform \
            .
        '''
      }
    }

    stage('Scan') {
      steps {
        // Gate on CRITICAL with a fix available; unfixed CVEs fail
        // nothing (there is no action to take) but still print.
        sh 'trivy image --exit-code 1 --severity CRITICAL --ignore-unfixed "$IMAGE_REPO:$GIT_SHA"'
      }
    }

    stage('Push') {
      when { branch 'main' }
      steps {
        withCredentials([usernamePassword(credentialsId: 'ghcr-push',
                                          usernameVariable: 'REG_USER',
                                          passwordVariable: 'REG_TOKEN')]) {
          sh '''
            echo "$REG_TOKEN" | docker login ghcr.io -u "$REG_USER" --password-stdin
            docker push "$IMAGE_REPO:$GIT_SHA"
          '''
        }
      }
    }

    stage('Deploy') {
      when { branch 'main' }
      steps {
        withCredentials([file(credentialsId: 'k3s-kubeconfig', variable: 'KUBECONFIG')]) {
          sh '''
            # Stamp the workspace copy of the chart so the APP VERSION
            # column in `helm history` names the build each revision
            # actually deployed — the moment you read that column is the
            # moment it must not lie. The committed Chart.yaml keeps the
            # last-released appVersion as the manual-install fallback;
            # this checkout is disposable.
            sed -i "s/^appVersion:.*/appVersion: \\"$GIT_SHA\\"/" kubernetes/helm/taskflow/Chart.yaml
            helm upgrade taskflow kubernetes/helm/taskflow -n taskflow \
              -f kubernetes/helm/taskflow/values-prod.yaml \
              --set image.tag="$GIT_SHA" \
              --wait --timeout 5m
          '''
        }
      }
    }

    stage('Smoke test') {
      when { branch 'main' }
      steps {
        withCredentials([file(credentialsId: 'k3s-kubeconfig', variable: 'KUBECONFIG')]) {
          sh '''
            # The k3s API host in the kubeconfig is the app node's
            # private IP — same box serves the Ingress on port 80.
            APP_HOST=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}' \
                       | sed -E 's#^https://##; s#:6443$##')
            curl -fsS -m 10 "http://${APP_HOST}/healthz"
            DEPLOYED=$(kubectl -n taskflow get deployment taskflow \
                       -o jsonpath='{.spec.template.spec.containers[0].image}')
            if [ "$DEPLOYED" != "$IMAGE_REPO:$GIT_SHA" ]; then
              echo "deployed image $DEPLOYED does not match built $IMAGE_REPO:$GIT_SHA"
              exit 1
            fi
            echo "smoke test OK: $DEPLOYED is live"
          '''
        }
      }
    }
  }

  post {
    always {
      // Leave the node as found: no session, no stale build layers, no
      // workspace eating the disk.
      sh 'docker logout ghcr.io >/dev/null 2>&1 || true'
      // Tagged app images accumulate one per deploy and `prune` only
      // touches dangling layers — keep the newest three (current,
      // rollback, one spare) and drop the rest.
      sh '''
        docker images "$IMAGE_REPO" --format "{{.Tag}}" \
          | tail -n +4 | xargs -r -I{} docker rmi "$IMAGE_REPO:{}" || true
      '''
      sh 'docker image prune -f --filter "until=24h" >/dev/null 2>&1 || true'
      deleteDir()
    }
  }
}
