import time
import sys
import requests

# URL do servidor coordenador Mestre (Flask).
# OBS: ainda usando o IP/hostname físico (localhost). A resolução via DNS
# logico (mestre-crack.local), prevista no relatorio, sera tratada em uma
# implementacao futura.
MESTRE_URL = "http://mestre-crack.local:5000"

INTERVALO_CONSULTA_SEGUNDOS = 3


def obter_hash_do_usuario():
    """Pede ao usuário o hash MD5 alvo a ser quebrado."""
    print("=" * 60)
    print(" DISTRICRACK - Cliente")
    print("=" * 60)
    hash_informado = input("Digite o hash MD5: ").strip()
    return hash_informado


def enviar_hash_ao_mestre(hash_alvo):
    """Envia o hash alvo para o Mestre via POST, disparando a quebra distribuída."""
    try:
        url = f"{MESTRE_URL}/api/iniciar"
        response = requests.post(url, json={"hash": hash_alvo})
        dados = response.json()

        if response.status_code == 201 and dados.get("ok"):
            return True
        else:
            print(f"[ERRO] O Mestre rejeitou a requisição: {dados.get('erro', 'erro desconhecido')}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"[ERRO] Não foi possível conectar ao Mestre em {MESTRE_URL}. "
              f"Verifique se o mestre.py está rodando.")
        return False
    except Exception as e:
        print(f"[ERRO] Falha inesperada ao contactar o Mestre: {e}")
        return False


def consultar_resultado():
    """Consulta o Mestre para saber o status atual e, se concluído, o resultado."""
    try:
        response = requests.get(f"{MESTRE_URL}/api/resultado")
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"[ERRO] Falha ao consultar o resultado no Mestre: {e}")
    return None


def aguardar_termino():
    """Fica consultando o Mestre periodicamente até a execução terminar,
    e então exibe o resultado final ao usuário."""
    print("[CLIENTE] Aguardando o término do processamento distribuído...")

    while True:
        dados = consultar_resultado()

        if dados and dados.get("status") == "finalizado":
            senha = dados.get("senha")
            print("\n" + "=" * 60)
            print(f" SENHA ENCONTRADA: {senha}")
            print("=" * 60)
            return

        time.sleep(INTERVALO_CONSULTA_SEGUNDOS)


def main():
    hash_alvo = obter_hash_do_usuario()

    if not enviar_hash_ao_mestre(hash_alvo):
        sys.exit(1)

    aguardar_termino()


if __name__ == "__main__":
    main()
