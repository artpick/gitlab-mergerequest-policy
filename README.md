## Merge request script usage

The script has three arguments:
1. git project ssh url : **git@XXX:other/YYY.git**
1. project version : **1.0.0**
1. dev branch name : **dev**
1. rc branch name : **rc**

```bash
merge_request.py git@XXX:other/YYY.git 1.0.0 dev rc
```

Usage in Jenkins:

```bash
RELEASE_VERSION=$(mvn org.apache.maven.plugins:maven-help-plugin:2.1.1:evaluate -Dexpression=project.version | grep -v '\[')
echo $GIT_URL $RELEASE_VERSION
git add .
git commit -m "Finalize the version $RELEASE_VERSION"
git push origin dev

python /ZZZZ/merge_request.py $GIT_URL $RELEASE_VERSION dev rc
```
