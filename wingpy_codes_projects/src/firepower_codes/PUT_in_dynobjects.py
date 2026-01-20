from wingpy import CiscoFMC

FMC_URL = "https://192.168.3.122"
USERNAME = "admin"
PASSWORD = "Liopqwe19!#%"

def validate_ip(ip):
    import ipaddress
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def put_ip_in_dynamic_object(fmc, object_id, ip):
    resp = fmc.get(f"/api/fmc_config/v1/domain/{{domainUUID}}/object/dynamicobjects/{object_id}")
    obj = resp.json()
    values = obj.get("value")
    if values is not None:
        if ip in values:
            print(f"IP {ip} findes allerede i objektet.")
            return
        values.append(ip)
        obj["value"] = values
        obj.pop("links", None)
        obj.pop("metadata", None)
        put_resp = fmc.put(f"/api/fmc_config/v1/domain/{{domainUUID}}/object/dynamicobjects/{object_id}", data=obj)
        print(f"PUT status: {put_resp.status_code}")
        print(f"PUT response: {put_resp.text}")
        if put_resp.status_code == 200:
            print(f"✅ IP {ip} tilføjet til objekt {object_id}")
        else:
            print(f"❌ Fejl: {put_resp.status_code} - {put_resp.text}")
    else:
        print("Dette Dynamic Object understøtter ikke value-feltet. Kan ikke opdatere via API.")

if __name__ == "__main__":
    object_id = input("Indtast Object ID: ")
    new_ip = input("Indtast IP-adresse der skal tilføjes: ")
    if not validate_ip(new_ip):
        print("❌ Ugyldig IP-adresse. Prøv igen.")
        exit(1)
    fmc = CiscoFMC(base_url=FMC_URL, username=USERNAME, password=PASSWORD, verify=False)
    put_ip_in_dynamic_object(fmc, object_id, new_ip)