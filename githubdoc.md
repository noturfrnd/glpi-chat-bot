# Tutorial github

Para iniciar no uso do github, primeiro você deve clonar o projeto em https://github.com/noturfrnd/glpi-chat-bot, pra isso basta clicar no botao escrito <>CODE e seguir o passo a passo apresentado.

## Criando sua propria branch

Pra começar a trabalhar com o codigo, voce deve seguir um breve passo a passo que vai garantir que você tenha todas as ultimas alterações feitas por seus colegas no seu codigo e que possa trabalhar sem medo de perder suas mudanças

 - Primeiro, tenha certeza que voce esta na branch "main"
 isso vai garantir que você esta onde todos vao atualizar as mudanças trabalhada

### pela IDE (vsCode)

  - para saber em qual branch voce esta agora, basta olhar para o canto inferior esquerdo do vsCode ![alt text](image-2.png) 
  no meu caso "api-return" é a branch

  - Para mudar de branch basta clicar no nome, vai abrir no topo do vsCode uma lista de branchs, onde voce deve escoher "main" ![alt text](image-7.png) ao clicar em main, toda a mudança sera feita automaticamente

  - agora voce precisa atualizar as mudanças que estão na main da nuvem para o seu codigo local

    -


### no terminal

   - para isso, abra o powershell, gitbash ou prompt de comando a partir do arquivo do codigo, o promp aberto ira se parecer com isso ![alt text](image.png) para o gitbash, ja para o powershell: ![alt text](image-1.png)
   - No caso do gitbash o texto em azul indica a branch que você esta, no meu caso (api-return) tenha certeza de estar na main
   - no caso do powershell você pode utilizar o comando git status para visualizar sua branch atual
   - caso nao esteja na main, basta executar o comando `git checkout main`

 - No gitbash, powershell ou prompt de comando, execute o comando `git pull` para que toda a atualização da nuvem seja baixada para o seu codigo local

 - enfirm, basta que neste mesmo terminal você execute o comando `git checkout -b "Nome da branch nova"` adicionando o nome da branch que deseja criar,
 atenção para criar branchs com nomes que façam sentido, se Paulo for trabalhar por exemplo no endpoint de aprovação seria 
 `git checkout -b "paulo/endpoint-aprovacao"`

 - depois disso voce ira notar no canto do seu editor (VSCODE) que o nome da branch mudou![alt text](image-2.png)
 
 - ao terminar de fazer as alterações voce pode adicionar na nuvem as suas mudanças com os seguintes comandos: 

   - git status (esse comando vai mostrar os arquivos modificados)![alt text](image-3.png)
   - git add . (esse comando vai adicionar todas as modificaçoes aos arquivos que serão enviados a nuvem)![alt text](image-4.png)
   - git commit -m "mensagem" (esse comando é obrigatorio e vai pegar todos os arquivos marcados pra serem enviados à nuvem e encapsula-los em um 'commit', escolha a mensagem do commit com sabedoria)![alt text](image-5.png)
   - git push (esse comando ira pegar o commit criado anteriormente e adicionara ele à nuvem do github, depois desse, o codigo ja é acessivel atraves do site github)![alt text](image-6.png)