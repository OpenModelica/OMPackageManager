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
      docker {
        image 'openmodelica/openmodelica:v1.14.1-gui'
        label 'linux'
        args "-v /var/lib/jenkins/gitcache:/var/lib/jenkins/gitcache"
      }
    }
    environment {
      HOME = '/tmp/dummy'
    }
    steps {
      sh 'mkdir -p /var/lib/jenkins/gitcache/OMPackageManager'
      sh 'ln -s /var/lib/jenkins/gitcache/OMPackageManager cache'
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
        sh 'git commit -m "Updated libraries" rawdata.json'
        sh 'git push github master'
      }
      sshPublisher(publishers: [sshPublisherDesc(configName: 'PackageIndex', transfers: [sshTransfer(sourceFiles: 'index.json', remoteDirectory: 'v1')])])
    }
  }
  }
}
