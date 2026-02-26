.PHONY: up demo-allow demo-deny

up:
	docker compose up -d --build postgres redis api purchase-target

demo-allow:
	docker compose run --rm -e DEMO_MODE=allow agent-demo

demo-deny:
	docker compose run --rm -e DEMO_MODE=deny agent-demo
