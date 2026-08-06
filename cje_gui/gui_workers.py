from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot, Qt
from PySide6.QtWidgets import QApplication


class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(object)


class ApiWorker(QRunnable):
    """Ejecuta una llamada de red en un hilo del pool y emite el resultado
    (o el error) hacia el hilo de la interfaz. Nunca bloquea la UI."""

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            self.signals.error.emit(e)
        else:
            self.signals.result.emit(result)


_ACTIVE_WORKERS = set()


def _release(worker):
    """Libera la referencia al worker para permitir su recolección."""
    _ACTIVE_WORKERS.discard(worker)


def run_async(fn, on_result=None, on_error=None):
    """Despacha `fn` al pool de hilos. Los callbacks corren en el hilo de la UI.

    Se mantiene una referencia fuerte al worker mientras corre; sin ella, el
    wrapper de Python (y sus señales) puede ser recolectado antes de que el hilo
    del pool ejecute `run()`, perdiendo el resultado de forma intermitente.
    """
    worker = ApiWorker(fn)
    if on_result is not None:
        worker.signals.result.connect(on_result)
    if on_error is not None:
        worker.signals.error.connect(on_error)
    worker.signals.result.connect(lambda _: _release(worker))
    worker.signals.error.connect(lambda _: _release(worker))
    _ACTIVE_WORKERS.add(worker)
    QThreadPool.globalInstance().start(worker)


_busy_count = 0


def push_busy():
    """Muestra el cursor de ocupado; seguro ante llamadas anidadas."""
    global _busy_count
    if _busy_count == 0:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    _busy_count += 1


def pop_busy():
    global _busy_count
    if _busy_count > 0:
        _busy_count -= 1
    if _busy_count == 0:
        QApplication.restoreOverrideCursor()
