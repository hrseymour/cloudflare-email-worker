/**
 * Email Worker with R2 Backup for Failed Forwards
 * Captures emails that fail to forward and stores them in R2
 * 
 * @author Harlan Seymour
 * @description Forwards emails to specified addresses and captures failed forwards
 */

// ============================================================================
// CONFIGURATION - Update this section for your email addresses
// ============================================================================

const EMAIL_CONFIG = {
  'harlan@harlanseymour.com': {
    forwardTo: 'hrseymour@gmail.com',
    enabled: true
  },
  'test@harlanseymour.com': {
    forwardTo: 'your-test-email@gmail.com',
    enabled: false  // Set to true when ready to use
  }
};

// R2 bucket binding name (from wrangler.toml)
const R2_BINDING = 'FAILED_EMAILS';

// ============================================================================
// WORKER CODE - No need to modify below this line
// ============================================================================

export default {
  async email(message, env, ctx) {
    const messageFrom = message.from;
    const messageTo = message.to.toLowerCase();  // Normalize to lowercase
    
    // Find matching email configuration
    const config = findEmailConfig(messageTo);
    
    if (!config) {
      console.log(`✗ No configuration found for recipient: ${messageTo}`);
      // Reject the email since we don't know what to do with it
      await message.setReject(`No email routing configured for ${messageTo}`);
      return;
    }
    
    if (!config.enabled) {
      console.log(`✗ Email routing disabled for: ${messageTo}`);
      await message.setReject(`Email routing is currently disabled for ${messageTo}`);
      return;
    }
    
    try {
      // Attempt to forward the email
      await message.forward(config.forwardTo);
      
      console.log(`✓ Successfully forwarded email from ${messageFrom} to ${config.forwardTo} (recipient: ${messageTo})`);
      
    } catch (error) {
      // Forwarding failed - capture and store the email
      console.error(`✗ Failed to forward email from ${messageFrom} to ${config.forwardTo}. Reason: ${error.message}`);
      
      // Don't wait for R2 storage - use ctx.waitUntil to handle async
      ctx.waitUntil(
        (async () => {
          try {
            await storeFailedEmail(message, env, error, config);
          } catch (storageError) {
            console.error('Failed to store email in R2:', storageError);
          }
        })()
      );
    }
  }
};

/**
 * Find email configuration for a given recipient address (case-insensitive)
 */
function findEmailConfig(recipientEmail) {
  const normalizedEmail = recipientEmail.toLowerCase();
  
  for (const [configEmail, config] of Object.entries(EMAIL_CONFIG)) {
    if (configEmail.toLowerCase() === normalizedEmail) {
      return config;
    }
  }
  
  return null;
}

/**
 * Store the failed email in R2 with full content
 */
async function storeFailedEmail(message, env, error, config) {
  try {
    // Read the email content as a raw stream
    const rawEmail = await new Response(message.raw).text();
    
    // Parse email headers for metadata
    const headers = {};
    const headersList = [...message.headers];
    headersList.forEach(([key, value]) => {
      headers[key.toLowerCase()] = value;
    });
    
    // Create a comprehensive email record
    const emailRecord = {
      timestamp: new Date().toISOString(),
      from: message.from,
      to: message.to,
      intendedForwardTo: config.forwardTo,
      subject: headers['subject'] || '(No Subject)',
      errorReason: error.message,
      headers: headers,
      size: message.rawSize,
      rawContent: rawEmail
    };
    
    // Generate a unique filename with timestamp
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const sanitizedFrom = message.from.replace(/[^a-zA-Z0-9@.-]/g, '_');
    const sanitizedTo = message.to.replace(/[^a-zA-Z0-9@.-]/g, '_');
    const filename = `${sanitizedTo}/${timestamp}_from_${sanitizedFrom}.json`;
    
    // Get the R2 bucket from environment bindings
    const bucket = env[R2_BINDING];
    
    if (!bucket) {
      throw new Error(`R2 binding "${R2_BINDING}" not found in environment`);
    }
    
    // Store in R2
    await bucket.put(
      filename,
      JSON.stringify(emailRecord, null, 2),
      {
        customMetadata: {
          from: message.from,
          to: message.to,
          intendedForwardTo: config.forwardTo,
          subject: headers['subject'] || '(No Subject)',
          errorReason: error.message,
          timestamp: emailRecord.timestamp
        }
      }
    );
    
    console.log(`✓ Stored failed email in R2: ${filename}`);
    
  } catch (storageError) {
    console.error('Error storing email in R2:', storageError);
    throw storageError;
  }
}
