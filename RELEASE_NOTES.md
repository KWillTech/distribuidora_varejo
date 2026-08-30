# Adega do Bruninho 1.2.0

## Controle de Comandas

- Abertura identificada ou vinculada a cliente, com numeração atômica.
- Produtos por unidade e fardo com reserva atômica do estoque disponível.
- Controle otimista de concorrência por versão.
- Remoção e cancelamento com liberação de reservas e auditoria.
- Estados Aberta, Em atendimento, Aguardando pagamento, Finalizada e Cancelada.
- Fechamento integrado a vendas, caixa, pagamentos mistos e fiado.
- Tela própria, indicadores no Painel, relatório e conferência em PDF.

## Versão anterior

## Controle de Fiado e Contas de Clientes

- Fiado integral, parcial e misto no PDV, com vencimento obrigatório.
- Limite de crédito reservado atomicamente e bloqueios por situação do cliente.
- Contas a receber, pagamentos parciais, extrato imutável, estorno e renegociação.
- Recebimentos separados das vendas no caixa.
- Tela Fiado com indicadores, contas, recebimentos e extrato.
- Indicadores no Painel e relatório de envelhecimento exportável em Excel/PDF.
- Permissões específicas e auditoria das operações críticas.

## Base anterior

Primeira versão completa do sistema desktop varejista.

## Instalação

1. Extraia a pasta completa em um diretório com permissão de escrita.
2. Copie `.env.example` para `.env`.
3. Configure `MONGODB_URI` e `MONGODB_DATABASE` no `.env`.
4. Execute `AdegaDoBruninho.exe`.

O MongoDB deve estar acessível pela rede local. Não compartilhe o arquivo `.env`
nem inclua credenciais em chamados ou capturas de tela.

## Atualização

Feche o sistema em todas as estações que serão atualizadas, preserve o `.env` e
substitua os demais arquivos pela nova distribuição. Faça um backup validado
antes de atualizações em ambiente de produção.

## Verificação

O pacote foi aprovado em testes automatizados, compilação Python, build do
PyInstaller e smoke test do executável.
