'''
Created on Dec 29, 2021

@author: vladyslav_goncharuk
'''

from paf.paf_impl import logger, CommunicationMode, Task

class AndroidDeploymentTask(Task):

    def __init__(self):
        super().__init__()

        self.REPO_TOOL_PATH = "${ROOT}/${ANDROID_DEPLOYMENT_DIR}/${DOWNLOAD_DIR}/${REPO_TOOL_SUB_DIR}"
        self.ANDROID_SOURCE_PATH = "${ROOT}/${ANDROID_DEPLOYMENT_DIR}/${SOURCE_DIR}/${ANDROID_REPO_BRANCH}"
        self.ANDROID_BUILD_DIR = "${ROOT}/${ANDROID_DEPLOYMENT_DIR}/${BUILD_DIR}/"
        self.ANDROID_BUILD_PATH = "${ROOT}/${ANDROID_DEPLOYMENT_DIR}/${BUILD_DIR}/${ANDROID_REPO_BRANCH}"
        self.REPO_SYNCED_TOOL_PATH = "${ROOT}/${ANDROID_DEPLOYMENT_DIR}/${SOURCE_DIR}/${ANDROID_REPO_BRANCH}/.repo/repo"
        self.VENDOR_PATH = "${ROOT}/${ANDROID_DEPLOYMENT_DIR}/${SOURCE_DIR}/${ANDROID_REPO_BRANCH}/${LOCAL_VENDOR_DESTINATION_PATH}"

class android_init(AndroidDeploymentTask):

    def __init__(self):
        super().__init__()
        self.set_name(android_init.__name__)

    def execute(self):

        logger.info("Get initial repo binary from Google")
        self.subprocess_must_succeed(
            f"mkdir -p {self.REPO_TOOL_PATH} && cd {self.REPO_TOOL_PATH}; " +
            f"if test -e \"./repo\"; then zflag='--time-cond repo'; else zflag=''; fi; touch ./repo; "
            f" curl \"https://storage.googleapis.com/git-repo-downloads/repo\" $${{zflag}} --output repo && " +
            f" chmod a+x {self.REPO_TOOL_PATH}/repo")

        logger.info("Check of the git user name/email configuration")

        self.subprocess_must_succeed('git config user.name; if [ $$? -ne 0 ]; then '
            'echo "A git user name should be configured for later build steps. '
            'You seem to be running outside of container, because the container should have it configured already. '
            'Therefore, please note that what you provide here will be stored in the global git settings (in your home directory!)"; '
            'read -p "Name: " name; git config --global user.name "$$name"; fi')

        logger.info("Init and sync repo")
        self.subprocess_must_succeed("git config user.email; if [ $$? -ne 0 ]; then "
            'echo "A git user email should be configured for later build steps. '
            'You seem to be running outside of container, because the container should have it configured already. '
            'Therefore, please note that what you provide here will be stored in the global git settings (in your home directory!)"; '
            'read -p "Email: " email; git config --global user.email "$$email"; fi')

        self.subprocess_must_succeed(f"mkdir -p {self.ANDROID_SOURCE_PATH} && cd {self.ANDROID_SOURCE_PATH}; "
                                     f"{self.REPO_TOOL_PATH}/repo init" +
                                     f"{' -u ' + '${ANDROID_REPO_URL}' if (hasattr(self, 'ANDROID_REPO_URL') and self.ANDROID_REPO_URL) else ''}" +
                                     f"{' -b ' + '${ANDROID_REPO_BRANCH}' if (hasattr(self, 'ANDROID_REPO_BRANCH') and self.ANDROID_REPO_BRANCH) else ''}" +
                                     f"{' -m ' + '${ANDROID_MANIFEST}' if (hasattr(self, 'ANDROID_MANIFEST') and self.ANDROID_MANIFEST) else ''}")

        if self.has_non_empty_environment_param("ANDROID_LOCAL_MANIFESTS_GIT_URL"):
            logger.info("ANDROID_LOCAL_MANIFESTS_GIT_URL is specified. Let's clone the local manifest")
            self.subprocess_must_succeed(f"cd {self.ANDROID_SOURCE_PATH} && rm -rf .repo/local_manifests && mkdir -p .repo/local_manifests && git clone" + " ${ANDROID_LOCAL_MANIFESTS_GIT_URL} .repo/local_manifests")

        self.subprocess_must_succeed(f"cd {self.ANDROID_SOURCE_PATH} && {self.REPO_SYNCED_TOOL_PATH}/repo sync " + "-j${BUILD_SYSTEM_CORES_NUMBER}")

        if self.has_non_empty_environment_param("PATCH_AFTER_REPO_SYNC_HOOK") and \
        self.has_non_empty_environment_param("PATCH_AFTER_REPO_SYNC_HOOK"):         
            self.subprocess_must_succeed(self.PATCH_AFTER_REPO_SYNC_HOOK)

class android_build(AndroidDeploymentTask):
    def __init__(self):
        super().__init__()
        self.set_name(android_build.__name__)

    def execute(self):

        if self.has_non_empty_environment_param("LOCAL_VENDOR_DESTINATION_PATH") and \
        self.has_non_empty_environment_param("LOCAL_VENDOR_SOURCE_PATH"):
            self.subprocess_must_succeed(f"cd {self.ANDROID_SOURCE_PATH} && mkdir -p " + "${LOCAL_VENDOR_DESTINATION_PATH}; rm -rf ${LOCAL_VENDOR_DESTINATION_PATH}/* " + "&& cp -r ${LOCAL_VENDOR_SOURCE_PATH}/* " + f"{self.VENDOR_PATH}")

        self.subprocess_must_succeed(f"cd {self.ANDROID_SOURCE_PATH} && . ./build/envsetup.sh; "
                                     f"export OUT_DIR_COMMON_BASE={self.ANDROID_BUILD_DIR}; "
                                    "lunch ${ANDROID_LUNCH_CONFIG} && make showcommands -j${BUILD_SYSTEM_CORES_NUMBER}",
                                     communication_mode = CommunicationMode.PIPE_OUTPUT)

class android_run_emulator(AndroidDeploymentTask):
    def __init__(self):
        super().__init__()
        self.set_name(android_run_emulator.__name__)

    def execute(self):

        wipe_data_param = ""

        if self.has_environment_true_param("WIPE_DATA"):
            wipe_data_param = " -wipe-data"

        self.subprocess_must_succeed(f"export OUT_DIR_COMMON_BASE={self.ANDROID_BUILD_DIR}; cd {self.ANDROID_SOURCE_PATH} && . ./build/envsetup.sh && lunch " 
                                     "${ANDROID_LUNCH_CONFIG}; " + f"emulator{wipe_data_param} -qemu")
