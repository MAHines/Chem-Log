# Chem Log App – A Mac app to log attendance in lab. 

The app should be run on a computer with a USB card reader. Students swipe their ID cards on 
entry. Their ID, a datetime stamp, and some additional data are stored on a Google sheet for
later processing.

This is a severless streamlit app based on stlite/desktop (https://stlite.net). The package
runs entirely in a browser and does not require installation of Python, Pandas, etc. Instead
the package runs in Pyodide.

I had difficulty using nvm to install stlite on a Mac, but yarn worked flawlessly.

Useful resources:

https://github.com/whitphx/stlite

Building a stlite app
https://www.youtube.com/watch?v=3wZ7GRbr91g

Notarizing an Electron App
https://kilianvalkhof.com/2019/electron/notarizing-your-electron-application/