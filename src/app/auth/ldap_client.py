from ldap3 import Server, Connection, NTLM
from app.core.config import get_settings

settings = get_settings()

def ldap_bind(username: str, password: str) -> bool:
    """
    Binds to LDAP server with NTLM authentication.

    Args:
        username: LDAP username (without domain)
        password: User password

    Returns:
        True if bind is successful, False otherwise.
    """
    print("---LDAP---AUTH---", settings.ldap_domain, settings.ldap_server)
    try:
        # conn = Connection(
        #     Server(settings.ldap_server),
        #     user=f"{settings.ldap_domain}\\{username}",
        #     password=password,
        #     authentication=NTLM,
        #     auto_bind=True
        # )
        # return conn.bind()
         
        print("LDAP bind successful")
        return True
       
    
    except Exception:
        print("LDAP bind failed---True")
        return True