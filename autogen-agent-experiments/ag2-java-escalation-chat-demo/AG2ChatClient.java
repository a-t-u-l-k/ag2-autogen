import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

// Using org.json library for JSON handling
import org.json.JSONObject;

public class AG2ChatClient {
    private final String serverUrl;
    private final String username;
    private final String password;
    private final HttpClient httpClient;

    public AG2ChatClient(String serverUrl, String username, String password) {
        this.serverUrl = serverUrl;
        this.username = username;
        this.password = password;
        
        // Create HTTP client
        this.httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .build();
    }

    /**
     * Send a message to the AG2 server and get the response
     * @param message The user message to send
     * @return ChatResponse containing the agent's response and sentiment data
     * @throws IOException If there's an IO error
     * @throws InterruptedException If the operation is interrupted
     */
    public ChatResponse sendMessage(String message) throws IOException, InterruptedException {
        // Create JSON request body for message
        JSONObject requestBody = new JSONObject();
        requestBody.put("message", message);
        
        // Create Basic Auth header
        String authHeaderValue = "Basic " + Base64.getEncoder().encodeToString(
            (username + ":" + password).getBytes(StandardCharsets.UTF_8)
        );
        
        // Debug the request being sent
        System.out.println("Sending request to: " + serverUrl + "/chat");
        System.out.println("Request body: " + requestBody.toString());
        
        // Create and send HTTP request
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(serverUrl + "/chat"))
            .header("Content-Type", "application/json")
            .header("Authorization", authHeaderValue)
            .POST(HttpRequest.BodyPublishers.ofString(requestBody.toString()))
            .build();
        
        // Send request and get response
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        
        // Debug the response
        System.out.println("Response status: " + response.statusCode());
        System.out.println("Response body: " + response.body());
        
        // Handle error responses
        if (response.statusCode() != 200) {
            throw new IOException("Error from server: " + response.statusCode() + " " + response.body());
        }
        
        // Parse JSON response
        JSONObject responseJson = new JSONObject(response.body());
        
        return new ChatResponse(
            responseJson.getString("response"),
            responseJson.getString("responder_type"),
            responseJson.getDouble("user_sentiment"),
            responseJson.getDouble("agent_sentiment")
        );
    }
    
    /**
     * Send a debug request to see what the server receives
     */
    public String debugRequest() throws IOException, InterruptedException {
        // Create Basic Auth header
        String authHeaderValue = "Basic " + Base64.getEncoder().encodeToString(
            (username + ":" + password).getBytes(StandardCharsets.UTF_8)
        );
        
        JSONObject testBody = new JSONObject();
        testBody.put("test", "value");
        
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(serverUrl + "/debug"))
            .header("Content-Type", "application/json")
            .header("Authorization", authHeaderValue)
            .POST(HttpRequest.BodyPublishers.ofString(testBody.toString()))
            .build();
        
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        return response.body();
    }
    
    /**
     * Reset the conversation history on the server
     * @throws IOException If there's an IO error
     * @throws InterruptedException If the operation is interrupted
     */
    public void resetConversation() throws IOException, InterruptedException {
        String authHeaderValue = "Basic " + Base64.getEncoder().encodeToString(
            (username + ":" + password).getBytes(StandardCharsets.UTF_8)
        );
        
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(serverUrl + "/reset"))
            .header("Authorization", authHeaderValue)
            .POST(HttpRequest.BodyPublishers.noBody())
            .build();
        
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        
        if (response.statusCode() != 200) {
            throw new IOException("Error from server: " + response.statusCode() + " " + response.body());
        }
    }
    
    /**
     * Response class to encapsulate the AG2 server response
     */
    public static class ChatResponse {
        private final String response;
        private final String responderType; // "agent" or "supervisor"
        private final double userSentiment;
        private final double agentSentiment;
        
        public ChatResponse(String response, String responderType, double userSentiment, double agentSentiment) {
            this.response = response;
            this.responderType = responderType;
            this.userSentiment = userSentiment;
            this.agentSentiment = agentSentiment;
        }
        
        public String getResponse() {
            return response;
        }
        
        public String getResponderType() {
            return responderType;
        }
        
        public double getUserSentiment() {
            return userSentiment;
        }
        
        public double getAgentSentiment() {
            return agentSentiment;
        }
        
        @Override
        public String toString() {
            return "ChatResponse{" +
                   "response='" + response + '\'' +
                   ", responderType='" + responderType + '\'' +
                   ", userSentiment=" + userSentiment +
                   ", agentSentiment=" + agentSentiment +
                   '}';
        }
    }

    /**
     * Simple example of using the client with error handling and debugging
     */
    public static void main(String[] args) {
        try {
            // Replace with actual server URL and credentials
            AG2ChatClient client = new AG2ChatClient("http://localhost:8000", System.getenv().getOrDefault("AG2_API_USERNAME", "<set-api-username>"), System.getenv().getOrDefault("AG2_API_PASSWORD", "<set-api-password>"));
            
            // Debug request
            try {
                System.out.println("Debug response: " + client.debugRequest());
            } catch (Exception e) {
                System.out.println("Debug request failed: " + e.getMessage());
                e.printStackTrace();
            }
            
            // Example conversation
            try {
                ChatResponse response1 = client.sendMessage("I'm interested in your premium subscription. What features does it include?");
                System.out.println("Response from " + response1.getResponderType() + ": " + response1.getResponse());
                System.out.println("User sentiment: " + response1.getUserSentiment());
                System.out.println("Agent sentiment: " + response1.getAgentSentiment());
            } catch (Exception e) {
                System.out.println("Chat request failed: " + e.getMessage());
                e.printStackTrace();
            }
            
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
