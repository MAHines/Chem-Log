# Chem Log App – A Mac app to log lab attendance 

The app should be run on a computer with a USB card reader. Students swipe their ID cards on entry. Their ID, a datetime stamp, and some additional data are stored on a Google sheet for later processing.

This is a severless streamlit app based on stlite/desktop (https://stlite.net). The package runs entirely in a browser and does not require installation of Python, Pandas, etc. Instead the package runs in Pyodide.

The app stores its data in multiple sheets within a Google worksheet. The API is described [by Google](https://developers.google.com/workspace/sheets/api/quickstart/python) and by [streamlit](https://docs.streamlit.io/develop/tutorials/databases/private-gsheet). Access is controlled by a secrets file that is not archived (for obvious reasons) but is located at ./.streamlit/secrets.toml.

The app was notarized using credentials stored in the keychain. The general form of the command is:

```xcrun notarytool store-credentials "chem-log-password-profile" --apple-id "..." --team-id "..." --password "...",```

where chem-log-password-profile is the name of the key in Keychain, and "..." represents redacted information. The password above uses an [app-specific password](https://support.apple.com/en-us/102654). This is called by assets/notarize.js and "afterSign": "./assets/notarize.js" in package.json.

The goal is to turn this into a Windoze app for deployment on random unused laptops.

I had difficulty using nvm to install stlite on a Mac, but yarn worked flawlessly.

For reasons that are unclear, the yarn dump . command fails about 20% of the time with

```ValueError: Can't find a pure Python 3 wheel for: 'google-auth<2.42.0,>=2.15.0'```

Waiting 30 sec often resolves this issue.

### Useful resources:

[STLite documentation](https://github.com/whitphx/stlite)

[Building a stlite app](https://www.youtube.com/watch?v=3wZ7GRbr91g)

[Notarizing an Electron App](https://kilianvalkhof.com/2019/electron/notarizing-your-electron-application/)