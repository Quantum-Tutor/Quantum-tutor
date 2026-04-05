from locust import HttpUser, task, between

class QuantumUser(HttpUser):
    wait_time = between(1, 2)

    @task
    def chat_flow(self):
        self.client.post("/api/evaluar-respuesta", json={
            "student_id": "locust_user",
            "question_id": "q1",
            "answer": "test locust validation",
        })
