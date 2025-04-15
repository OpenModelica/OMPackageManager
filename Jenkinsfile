pipeline {
  agent none
  parameters {
    booleanParam(name: 'UPLOAD_AND_CACHE', defaultValue: true, description: 'Also do stages upload and cache')
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
      sh './updateinfo.py'
      sh './genindex.py'
      stash name: 'files', includes: 'index.json, rawdata.json'
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
        if ! ( git diff-index --quiet HEAD -- ); then
          git config user.name "OpenModelica Jenkins"
          git config user.email "openmodelicabuilds.ida@lists.liu.se"
          git commit -m "Updated libraries" rawdata.json
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
      sh "du -csh /var/www/libraries.openmodelica.org/cache/* || true"
      sh "cp /var/www/libraries.openmodelica.org/index/v1/index.json ."
      sh "./generate-cache.py --clean /var/www/libraries.openmodelica.org/cache"
      sh "du -csh /var/www/libraries.openmodelica.org/cache/*"
    }
  }
  }
}
