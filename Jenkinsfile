pipeline {
  agent none
  parameters {
    booleanParam(name: 'UPLOAD_AND_CACHE', defaultValue: true, description: 'Also do stages upload and cache')
    string(name: 'WASM_OMC', defaultValue: 'omc', description: 'An omc whose getExternalFunctions describes what the prebuilt wasm modules are built from; empty skips them')
  }
  options {
    newContainerPerStage()
  }
  environment {
    LC_ALL = 'C.UTF-8'
  }
  stages {
  stage('update') {
    agent {
      dockerfile {
        filename '.CI/OMPython/Dockerfile'
        label 'linux'
        args "-v /var/lib/jenkins/gitcache:/var/lib/jenkins/gitcache"
      }
    }
    environment {
      HOME = '/tmp/dummy'
      GITHUB_AUTH = credentials('OpenModelica-Hudson')
    }
    steps {
      sh '''
      mkdir -p /var/lib/jenkins/gitcache/OMPackageManager
      rm -f cache
      ln -s /var/lib/jenkins/gitcache/OMPackageManager cache
      '''
      sh 'test -f rawdata.json'
      sh 'python3 -m ompackagemanager updateinfo'
      sh 'python3 -m ompackagemanager genindex'
      script {
        if (params.WASM_OMC) {
          def status = sh(returnStatus: true, script: "python3 -m ompackagemanager build-wasm --omc '${params.WASM_OMC}' --output www-data/precompiled/wasm32-wasip1")
          sh 'python3 -m ompackagemanager genindex'
          if (status != 0) {
            unstable('build-wasm did not build everything')
          }
        }
      }
      stash name: 'files', includes: 'index.json, rawdata.json, wasmdata.json, www-data/precompiled/wasm32-wasip1/**', allowEmpty: true
    }
  }
  stage('upload') {
    agent {
      label 'linux'
    }
    when {
      beforeAgent true
      expression { params.UPLOAD_AND_CACHE }
    }
    environment {
      HOME = '/tmp/dummy'
    }
    steps {
      sshagent (credentials: ['Hudson-SSH-Key']) {
        unstash 'files'
        sh '''
        git remote add github git@github.com:OpenModelica/OMPackageManager.git || true
        git remote set-url github git@github.com:OpenModelica/OMPackageManager.git
        '''
        sh '''
        git update-index --refresh || true
        if test -f wasmdata.json; then git add wasmdata.json; fi
        if ! ( git diff-index --quiet HEAD -- ); then
          git config user.name "OpenModelica Jenkins"
          git config user.email "openmodelicabuilds.ida@lists.liu.se"
          git commit -m "Updated libraries" rawdata.json $(test -f wasmdata.json && echo wasmdata.json)
          GIT_SSH_COMMAND="ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no" git push github HEAD:master
        fi
        '''
      }
      sshPublisher(publishers: [sshPublisherDesc(configName: 'PackageIndex', transfers: [sshTransfer(sourceFiles: 'index.json', remoteDirectory: 'v1')])])
    }
  }
  stage('cache') {
    agent {
      label 'r630-2'
    }
    when {
      beforeAgent true
      expression { params.UPLOAD_AND_CACHE }
    }
    environment {
      HOME = '/tmp/dummy'
    }
    steps {
      unstash 'files'
      sh '''
      if test -d www-data/precompiled/wasm32-wasip1; then
        mkdir -p /var/www/libraries.openmodelica.org/precompiled/wasm32-wasip1
        cp -r www-data/precompiled/wasm32-wasip1/. /var/www/libraries.openmodelica.org/precompiled/wasm32-wasip1/
      fi
      '''
      sh "du -csh /var/www/libraries.openmodelica.org/cache/* || true"
      sh "cp /var/www/libraries.openmodelica.org/index/v1/index.json ."
      sh "python3 -m ompackagemanager generate-cache --clean /var/www/libraries.openmodelica.org/cache"
      sh "du -csh /var/www/libraries.openmodelica.org/cache/*"
    }
  }
  }
}
