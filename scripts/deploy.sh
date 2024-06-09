#!usr/bin/env bash
set -euf -o pipefail

# SOFTWEAR_HALLOUMI_CONFIG_ACCESS_TOKEN is set in the repo CI settings. It has read and
# write access to the softwear-halloumi-config repo
SENTIA_HALLOUMI_CONFIG_REPO=https://gitlab-ci-token:$SOFTWEAR_HALLOUMI_CONFIG_ACCESS_TOKEN@gitlab.com/softwearconnect/softwear-halloumi-config.git
SPYNL_EDGE_BUILD_URL="https://spynl.edge.softwearconnect.com/about/build"

VERSION=`git describe`

# Update and push the softwear-halloumi-config to trigger a build with
# Sentia production stack. This updates the test environment with them.
git clone $SENTIA_HALLOUMI_CONFIG_REPO
(
    cd softwear-halloumi-config

    sed -i "s#\(image.\) .*#\1 $SENTIA_IMAGE#" spynlapi.yml;
    sed -i "s#\(image.\) .*#\1 $SENTIA_IMAGE#" spynlservices.yml;

    if ! git diff --quiet; then
        git commit --all --message "Spynl build $VERSION"
        # Save a patch file for possible inspection.
        git format-patch -1 @ --unified=0 --stdout | tee ../patch
        git push $SENTIA_HALLOUMI_CONFIG_REPO HEAD:edge
    fi
)


# commenting this part out, because most of the time it times out before sentia manages to
# deploy, so the failure is a false negative.

# echo Verifying deployment of build $CI_COMMIT_SHORT_SHA on $SPYNL_EDGE_BUILD_URL
# echo This may take a while.

# while [ ${TRIES:=1} -lt 900 ]; do
#     printf  "."
#     if wget -qO- $SPYNL_EDGE_BUILD_URL | grep -q $CI_COMMIT_SHORT_SHA ; then
#         SUCCES=1
#         # Print check mark.
#         printf "\xE2\x9C\x94\n"
#         break
#     fi
#     ((TRIES+=1))
#     sleep 1
# done

# # Verify that it matches the current build.
# if [ ${SUCCES:-0} = 0 ]; then
#     echo "New build $CI_COMMIT_SHORT_SHA was not picked up."
#     exit 1
# fi
