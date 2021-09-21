pipeline {
  agent none
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
    environment {
      HOME = '/tmp/dummy'
    }
    steps {
      sshagent (credentials: ['Hudson-SSH-Key']) {
        unstash 'files'
        sh 'mkdir -p ~/.ssh/'
        sh 'ssh-keyscan github.com >> ~/.ssh/known_hosts'
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
          git push github HEAD:master
        fi
        '''
      }
      sshPublisher(publishers: [sshPublisherDesc(configName: 'PackageIndex', transfers: [sshTransfer(sourceFiles: 'index.json', remoteDirectory: 'v1')])])
    }
  }
  }
}
