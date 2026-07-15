# Seletores CSS e XPath para automação com o Playwright no Portal Multiplike.
# Modifique os valores aqui caso a estrutura do portal seja alterada.

SELECTORS = {
    "login": {
        "email": [
            "[data-testid=login-form-email-input]",
            "#username",
            "input[type=email]",
            "input[name=username]",
            "input[name*=email i]",
            "input[name*=user i]",
            "input[name*=login i]",
        ],
        "senha": [
            "[data-testid=login-form-password-input]",
            "#password",
            "input[type=password]",
            "input[name=password]",
        ],
        "submit": [
            "[data-testid=login-form-submit-button]",
            "#kc-login",
            "button[type=submit]",
            "input[type=submit]",
            "button:has-text('Entrar')",
            "button:has-text('Login')",
            "button:has-text('Acessar')",
        ],
        "confirmar_2fa": [
            "button[type=submit]",
            "button:has-text('Confirmar')",
            "button:has-text('Validar')",
            "button:has-text('Entrar')",
        ]
    },
    "busca_cnpj": {
        # Confirmado via diagnóstico real na tela /scoremultiplike.
        "input_cnpj": [
            "input[name=document]",
            "input[name*=cnpj i]",
            "input[id*=cnpj i]",
            "input[placeholder*=cnpj i]",
        ],
        "submit": [
            "button[type=submit]",
            "button:has-text('Consultar')",
            "button:has-text('Buscar')",
            "button:has-text('Pesquisar')",
        ]
    },
    "score_navigation": {
        # Confirmado via diagnóstico real (modal "Selecione um perfil para continuar").
        "ir_para_cedente": [
            "text='Ir para portal do cedente'",
            "button:has-text('Ir para portal do cedente')",
        ],
        # Confirmado via diagnóstico real (card na home do portal do cedente).
        "score_card_button": [
            "[data-testid=home-card-score-multiplike-button]",
            "[data-testid=home-card-score-multiplike] button:has-text('Clique aqui')",
        ],
    }
}
