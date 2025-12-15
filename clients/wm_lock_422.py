from heros import RemoteHERO
from PyQt5.QtWidgets import QApplication

from wm_lock import WMLockClient


if __name__ == "__main__":
    with RemoteHERO("wm_lock_422") as server:
        try:
            app = QApplication([])
            window = WMLockClient(server)
            window.show()
            app.exec()
        except KeyboardInterrupt:
            pass
        