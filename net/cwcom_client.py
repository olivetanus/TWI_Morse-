# net/cwcom_client.py
"""
Shim per usare il client già presente in radice (cwcom_client.py).
Se NON esiste, prova a importare pykob o lancia un errore amichevole.
"""
try:
    from cwcom_client import CWComClient  # file già fornito in precedenza
except Exception as e:
    raise ImportError("Manca cwcom_client.py alla radice del progetto: aggiungilo o installa PyKOB.") from e
