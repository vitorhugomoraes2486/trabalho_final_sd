# Quebra_Senhas


O projeto final de Sistemas Disstribuídos, tem como objetivo a implementação de características que apresentarão uma possibilidade de escalamento horiontal do projeto, unido a transparência de localização dos nós.







Caracteríticas Utilizadas:
  - Transparência de Localização
    O cliente interage com a máquina principal, envia a senha a ser quebrada, e recebe o feedback, ele não precisa saber se o hash está sendo quebrado na CPU da     máquina A, na GPU da máquina B ou em um container rodando no WSL 2. O sistema distribuído age como se fosse um único computador centralizado perante o usuário.

  - Escalabilidade Horizontal
    O design do seu código deve permitir que novas instâncias do script do Worker se conectem ao Flask a qualquer momento da execução, sem precisar reiniciar o servidor principal.


<img width="532" height="664" alt="Arquitetura_password_cracker drawio" src="https://github.com/user-attachments/assets/e3957144-4ff3-4793-9147-24e0226446b8" />
