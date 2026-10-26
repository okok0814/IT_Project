"""One model-owning worker; request threads share its index and result cache."""
bind = "0.0.0.0:8000"
workers = 1
worker_class = "gthread"
threads = 4
timeout = 180
graceful_timeout = 30
accesslog = "-"
errorlog = "-"
capture_output = True
# Load Torch only inside the worker, avoiding a fork after model initialization.
preload_app = False
