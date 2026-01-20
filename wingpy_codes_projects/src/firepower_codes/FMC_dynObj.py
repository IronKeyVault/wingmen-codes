from wingpy import CiscoFMC

# Konfiguration
FMC_URL = "https://192.168.3.122"  # Udskift med din FMC URL
USERNAME = "admin"                   # Dit FMC brugernavn
PASSWORD = "Liopqwe19!#%"                # Dit FMC password

def main():
    # Opret FMC-klient
    fmc = CiscoFMC(
        base_url=FMC_URL,
        username=USERNAME,
        password=PASSWORD,
        verify=False  # Sæt til True hvis du har gyldigt certifikat
    )

    # Hent alle Dynamic Objects
    print("Henter Dynamic Objects fra FMC...")
    dynamic_objects = fmc.get_all("/api/fmc_config/v1/domain/{domainUUID}/object/dynamicobjects")

    # Print resultatet
    if dynamic_objects:
        print(f"Fundet {len(dynamic_objects)} Dynamic Objects:")
        for obj in dynamic_objects:
            print(f"- {obj.get('name')} (ID: {obj.get('id')})")
    else:
        print("Ingen Dynamic Objects fundet.")

if __name__ == "__main__":
    main()
