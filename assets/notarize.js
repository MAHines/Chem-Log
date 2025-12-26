require("dotenv").config();
const { notarize } = require("@electron/notarize");

exports.default = async function notarizing(context) {
  const { electronPlatformName, appOutDir } = context;
  if (electronPlatformName !== "darwin") {
    return;
  }

  const appName = context.packager.appInfo.productFilename;
  console.log(`Notarizing ${appName} in ${appOutDir}`);

  // Use notarytool as altool is deprecated
  // Ensure you set the environment variables below
  return await notarize({
    tool: "notarytool",
    appPath: `${appOutDir}/${appName}.app`,
    keychainProfile: "chem-log-password-profile",
  });
};