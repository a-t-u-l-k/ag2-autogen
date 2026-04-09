import java.util.Scanner;

public class ChatDemo {
    public static void main(String[] args) {
        // Configure client
        String serverUrl = "http://localhost:8000";
        String username = System.getenv().getOrDefault("AG2_API_USERNAME", "<set-api-username>");
        String password = System.getenv().getOrDefault("AG2_API_PASSWORD", "<set-api-password>");
        
        AG2ChatClient client = new AG2ChatClient(serverUrl, username, password);
        Scanner scanner = new Scanner(System.in);
        boolean running = true;
        
        System.out.println("=== AG2 Customer Service Chat ===");
        System.out.println("Type 'exit' to quit, 'reset' to reset conversation, or 'debug' to run diagnostics");
        System.out.println("----------------------------------------");
        
        try {
            // Run debug request on startup
            System.out.println("Running diagnostic check...");
            try {
                String debugResponse = client.debugRequest();
                System.out.println("Server diagnostic successful");
            } catch (Exception e) {
                System.out.println("Server diagnostic failed: " + e.getMessage());
                System.out.println("Make sure the server is running and accessible at " + serverUrl);
            }
            
            while (running) {
                System.out.print("You: ");
                String input = scanner.nextLine().trim();
                
                if (input.equalsIgnoreCase("exit")) {
                    running = false;
                    continue;
                }
                
                if (input.equalsIgnoreCase("reset")) {
                    client.resetConversation();
                    System.out.println("Conversation has been reset");
                    continue;
                }
                
                if (input.equalsIgnoreCase("debug")) {
                    try {
                        String debugResponse = client.debugRequest();
                        System.out.println("Debug response from server: " + debugResponse);
                    } catch (Exception e) {
                        System.out.println("Debug failed: " + e.getMessage());
                    }
                    continue;
                }
                
                // Send message to server
                try {
                    AG2ChatClient.ChatResponse response = client.sendMessage(input);
                    
                    // Display response
                    String responder = response.getResponderType().equals("supervisor") ? 
                                      "Supervisor" : "Agent";
                    
                    System.out.println(responder + ": " + response.getResponse());
                    System.out.println("----------------------------------------");
                    System.out.println("User sentiment: " + formatSentiment(response.getUserSentiment()));
                    System.out.println("Agent sentiment: " + formatSentiment(response.getAgentSentiment()));
                    System.out.println("----------------------------------------");
                } catch (Exception e) {
                    System.out.println("Error: " + e.getMessage());
                }
            }
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
            e.printStackTrace();
        } finally {
            scanner.close();
        }
        
        System.out.println("Chat session ended. Goodbye!");
    }
    
    private static String formatSentiment(double score) {
        String sentiment;
        if (score <= -0.5) sentiment = "Very Negative";
        else if (score < 0) sentiment = "Negative";
        else if (score == 0) sentiment = "Neutral";
        else if (score < 0.5) sentiment = "Positive";
        else sentiment = "Very Positive";
        
        return String.format("%.2f (%s)", score, sentiment);
    }
}
