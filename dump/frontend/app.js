

// // import React, { useState, useRef, useEffect } from 'react';
// // import ReactMarkdown from 'react-markdown';
// // import remarkGfm from 'remark-gfm';
// // import './App.css';

// // const API_BASE = 'http://localhost:8000';

// // function App() {
// //   const [messages, setMessages] = useState([
// //     { sender: 'bot', text: 'Hello! Ask a question or upload a polyp image for segmentation analysis.' }
// //   ]);
// //   const [input, setInput] = useState('');
// //   const [loading, setLoading] = useState(false);
// //   const [pendingImage, setPendingImage] = useState(null);
// //   const [pendingImageUrl, setPendingImageUrl] = useState(null);
// //   const fileInputRef = useRef(null);
// //   const messagesEndRef = useRef(null);

// //   useEffect(() => {
// //     messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
// //   }, [messages, loading]);

// //   useEffect(() => {
// //     return () => {
// //       if (pendingImageUrl) URL.revokeObjectURL(pendingImageUrl);
// //     };
// //   }, [pendingImageUrl]);

// //   const appendMessage = (message) => {
// //     setMessages((prev) => [...prev, message]);
// //   };

// //   // Updates the text or attributes of the last message in place while streaming
// //   const updateLastMessage = (updater) => {
// //     setMessages((prev) => {
// //       const next = [...prev];
// //       const lastIdx = next.length - 1;
// //       next[lastIdx] = updater(next[lastIdx]);
// //       return next;
// //     });
// //   };

// //   // ── Core streaming call: posts to /chat and renders each token/image as it arrives ──
// //   const streamChat = async (text, file) => {
// //     setLoading(true);

// //     // Placeholder bot bubble that will be filled token-by-token
// //     appendMessage({ sender: 'bot', text: '' });

// //     try {
// //       const formData = new FormData();
// //       formData.append('message', text || '');
// //       if (file) formData.append('file', file);

// //       const response = await fetch(`${API_BASE}/chat`, {
// //         method: 'POST',
// //         body: formData,
// //       });

// //       if (!response.ok || !response.body) {
// //         throw new Error('Server error while streaming response.');
// //       }

// //       const reader = response.body.getReader();
// //       const decoder = new TextDecoder('utf-8');
// //       let buffer = '';
// //       let firstToken = true;

// //       while (true) {
// //         const { done, value } = await reader.read();
// //         if (done) break;

// //         buffer += decoder.decode(value, { stream: true });

// //         // SSE frames are separated by a double newline \n\n
// //         let boundary;
// //         while ((boundary = buffer.indexOf('\n\n')) !== -1) {
// //           const rawFrame = buffer.slice(0, boundary);
// //           buffer = buffer.slice(boundary + 2);

// //           const eventLine = rawFrame.split('\n').find((l) => l.startsWith('event: '));
// //           const dataLine = rawFrame.split('\n').find((l) => l.startsWith('data: '));
// //           if (!eventLine || !dataLine) continue;

// //           const eventName = eventLine.replace('event: ', '').trim();
// //           const payload = JSON.parse(dataLine.replace('data: ', ''));

// //           if (eventName === 'meta') {
// //             if (payload.image_data) {
// //               // Format raw Base64 strings if necessary
// //               let formattedImage = payload.image_data;
// //               if (!formattedImage.startsWith('data:') && !formattedImage.startsWith('http')) {
// //                 formattedImage = `data:image/png;base64,${formattedImage}`;
// //               }
// //               updateLastMessage((m) => ({ ...m, image: formattedImage }));
// //             }
// //           } else if (eventName === 'token') {
// //             if (firstToken) {
// //               setLoading(false); // Hide loading indicator once tokens start flowing
// //               firstToken = false;
// //             }
// //             updateLastMessage((m) => ({ ...m, text: m.text + payload.text }));
// //           } else if (eventName === 'error') {
// //             updateLastMessage((m) => ({ ...m, text: payload.text }));
// //           } else if (eventName === 'done') {
// //             // Stream finished
// //           }
// //         }
// //       }
// //     } catch (error) {
// //       updateLastMessage((m) => ({ ...m, text: '⚠️ Server error while sending message. Ensure backend is running.' }));
// //     }

// //     setLoading(false);
// //   };

// //   const handleSendMessage = async () => {
// //     const text = input.trim();
// //     const fileToSend = pendingImage;

// //     if (!text && !fileToSend) return;

// //     // Append user message to chat UI
// //     appendMessage({
// //       sender: 'user',
// //       text: text || (fileToSend ? `[Uploaded Image: ${fileToSend.name}]` : ''),
// //       imageUrl: pendingImageUrl
// //     });

// //     // Reset input fields
// //     setInput('');
// //     setPendingImage(null);
// //     setPendingImageUrl(null);

// //     // Call streaming backend
// //     await streamChat(text, fileToSend);
// //   };

// //   const handleOpenFile = () => {
// //     fileInputRef.current?.click();
// //   };

// //   const handleImageSelect = (event) => {
// //     const file = event.target.files?.[0];
// //     if (!file) return;

// //     if (pendingImageUrl) URL.revokeObjectURL(pendingImageUrl);
// //     const previewUrl = URL.createObjectURL(file);

// //     setPendingImage(file);
// //     setPendingImageUrl(previewUrl);
// //     event.target.value = null; // reset file input
// //   };

// //   const handleRemovePendingImage = () => {
// //     if (pendingImageUrl) URL.revokeObjectURL(pendingImageUrl);
// //     setPendingImage(null);
// //     setPendingImageUrl(null);
// //   };

// //   return (
// //     <div style={{ maxWidth: '900px', margin: '0 auto', fontFamily: 'sans-serif', padding: '24px' }}>
// //       <h2 style={{ textAlign: 'center', color: '#222' }}>Polyp Segmentation & Analysis Assistant</h2>

// //       {/* Hidden File Input */}
// //       <input
// //         type="file"
// //         ref={fileInputRef}
// //         onChange={handleImageSelect}
// //         accept="image/*"
// //         style={{ display: 'none' }}
// //       />

// //       {/* Chat Messages Container */}
// //       <div style={{
// //         border: '1px solid #ddd',
// //         borderRadius: '12px',
// //         padding: '20px',
// //         height: '60vh',
// //         overflowY: 'auto',
// //         backgroundColor: '#fafafa'
// //       }}>
// //         {messages.map((msg, idx) => (
// //           <div key={idx} style={{ marginBottom: '18px', textAlign: msg.sender === 'user' ? 'right' : 'left' }}>
// //             <div style={{
// //               display: 'inline-block',
// //               padding: '12px 18px',
// //               borderRadius: '16px',
// //               backgroundColor: msg.sender === 'user' ? '#0b74de' : '#ffffff',
// //               color: msg.sender === 'user' ? '#fff' : '#111',
// //               boxShadow: '0 2px 5px rgba(0,0,0,0.05)',
// //               maxWidth: '85%',
// //               textAlign: 'left',
// //               border: msg.sender === 'user' ? 'none' : '1px solid #e0e0e0'
// //             }}>
// //               {/* Message Text */}
// //               {msg.sender === 'bot' ? (
// //                 <div className="markdown-body">
// //                   <ReactMarkdown remarkPlugins={[remarkGfm]}>
// //                     {msg.text || ' '}
// //                   </ReactMarkdown>
// //                 </div>
// //               ) : (
// //                 <div style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</div>
// //               )}

// //               {/* User Input Image Preview */}
// //               {msg.imageUrl && (
// //                 <div style={{ marginTop: '12px' }}>
// //                   <img src={msg.imageUrl} alt="Uploaded input" style={{ maxWidth: '100%', maxHeight: '300px', borderRadius: '10px', border: '1px solid #ccc' }} />
// //                 </div>
// //               )}

// //               {/* Bot Generated Segmentation Result Image */}
// //               {msg.image && (
// //                 <div style={{ marginTop: '12px' }}>
// //                   <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#666', marginBottom: '4px' }}>Segmentation Result:</div>
// //                   <img src={msg.image} alt="Segmentation result" style={{ width: '100%', borderRadius: '10px', border: '1px solid #ccc' }} />
// //                 </div>
// //               )}
// //             </div>
// //           </div>
// //         ))}
// //         {loading && <div style={{ color: '#007bff', fontStyle: 'italic', padding: '8px 0' }}>⏳ Processing segmentation model & streaming response...</div>}
// //         <div ref={messagesEndRef} />
// //       </div>

// //       {/* Pending Attached Image Preview Bar */}
// //       {pendingImageUrl && (
// //         <div style={{
// //           display: 'flex',
// //           alignItems: 'center',
// //           gap: '12px',
// //           marginTop: '12px',
// //           padding: '8px 12px',
// //           backgroundColor: '#eef6ff',
// //           borderRadius: '8px',
// //           border: '1px solid #b6d4fe'
// //         }}>
// //           <img src={pendingImageUrl} alt="Pending preview" style={{ width: '48px', height: '48px', objectFit: 'cover', borderRadius: '6px' }} />
// //           <span style={{ flex: 1, fontSize: '14px', color: '#333' }}>Ready to analyze: <strong>{pendingImage?.name}</strong></span>
// //           <button
// //             onClick={handleRemovePendingImage}
// //             style={{ border: 'none', background: 'transparent', color: '#d9534f', fontSize: '18px', cursor: 'pointer' }}
// //           >
// //             ✕
// //           </button>
// //         </div>
// //       )}

// //       {/* Bottom Control Bar */}
// //       <div style={{ display: 'flex', marginTop: '16px', gap: '10px' }}>
// //         <button
// //           type="button"
// //           onClick={handleOpenFile}
// //           disabled={loading}
// //           style={{
// //             padding: '12px 16px',
// //             backgroundColor: '#6c757d',
// //             color: '#fff',
// //             border: 'none',
// //             borderRadius: '10px',
// //             cursor: 'pointer',
// //             display: 'flex',
// //             alignItems: 'center',
// //             gap: '6px'
// //           }}
// //         >
// //           📷 Select Image
// //         </button>

// //         <input
// //           type="text"
// //           value={input}
// //           onChange={(e) => setInput(e.target.value)}
// //           onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
// //           placeholder="Type a message or prompt..."
// //           style={{ flex: 1, padding: '12px 14px', borderRadius: '10px', border: '1px solid #ccc' }}
// //         />

// //         <button
// //           onClick={handleSendMessage}
// //           disabled={(!input.trim() && !pendingImage) || loading}
// //           style={{
// //             padding: '12px 24px',
// //             background: loading ? '#a0c7ff' : '#007bff',
// //             color: '#fff',
// //             border: 'none',
// //             borderRadius: '10px',
// //             fontWeight: 'bold',
// //             cursor: loading ? 'not-allowed' : 'pointer'
// //           }}
// //         >
// //           Send
// //         </button>
// //       </div>
// //     </div>
// //   );
// // }

// // export default App;

// // import React, { useState, useRef, useEffect } from 'react';
// // import ReactMarkdown from 'react-markdown';
// // import remarkGfm from 'remark-gfm';
// // import './App.css';

// // const API_BASE = 'http://localhost:8000';

// // function App() {
// //   const [messages, setMessages] = useState([
// //     { sender: 'bot', text: 'Hello! Ask a question or upload a polyp image for segmentation analysis.' }
// //   ]);
// //   const [input, setInput] = useState('');
// //   const [loading, setLoading] = useState(false);
// //   const fileInputRef = useRef(null);
// //   const messagesEndRef = useRef(null);

// //   // 🟢 Image processing dialog state
// //   const [dialogOpen, setDialogOpen] = useState(false);
// //   const [dialogFileName, setDialogFileName] = useState('');
// //   const [dialogUserImageUrl, setDialogUserImageUrl] = useState(null); // uploaded image preview
// //   const [dialogBotText, setDialogBotText] = useState('');             // streamed text response
// //   const [dialogBotImage, setDialogBotImage] = useState(null);         // segmentation result image
// //   const [dialogLoading, setDialogLoading] = useState(false);

// //   useEffect(() => {
// //     messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
// //   }, [messages, loading]);

// //   useEffect(() => {
// //     return () => {
// //       if (dialogUserImageUrl) URL.revokeObjectURL(dialogUserImageUrl);
// //     };
// //   }, [dialogUserImageUrl]);

// //   const appendMessage = (message) => {
// //     setMessages((prev) => [...prev, message]);
// //   };

// //   const updateLastMessage = (updater) => {
// //     setMessages((prev) => {
// //       const next = [...prev];
// //       const lastIdx = next.length - 1;
// //       next[lastIdx] = updater(next[lastIdx]);
// //       return next;
// //     });
// //   };

// //   // ── Shared SSE stream parser: reads /chat response and fires callbacks per event ──
// //   const runChatStream = async (text, file, { onMeta, onToken, onError, onDone }) => {
// //     const formData = new FormData();
// //     formData.append('message', text || '');
// //     if (file) formData.append('file', file);

// //     const response = await fetch(`${API_BASE}/chat`, {
// //       method: 'POST',
// //       body: formData,
// //     });

// //     if (!response.ok || !response.body) {
// //       throw new Error('Server error while streaming response.');
// //     }

// //     const reader = response.body.getReader();
// //     const decoder = new TextDecoder('utf-8');
// //     let buffer = '';

// //     while (true) {
// //       const { done, value } = await reader.read();
// //       if (done) break;

// //       buffer += decoder.decode(value, { stream: true });

// //       let boundary;
// //       while ((boundary = buffer.indexOf('\n\n')) !== -1) {
// //         const rawFrame = buffer.slice(0, boundary);
// //         buffer = buffer.slice(boundary + 2);

// //         const eventLine = rawFrame.split('\n').find((l) => l.startsWith('event: '));
// //         const dataLine = rawFrame.split('\n').find((l) => l.startsWith('data: '));
// //         if (!eventLine || !dataLine) continue;

// //         const eventName = eventLine.replace('event: ', '').trim();
// //         const payload = JSON.parse(dataLine.replace('data: ', ''));

// //         if (eventName === 'meta' && payload.image_data) {
// //           let formattedImage = payload.image_data;
// //           if (!formattedImage.startsWith('data:') && !formattedImage.startsWith('http')) {
// //             formattedImage = `data:image/png;base64,${formattedImage}`;
// //           }
// //           onMeta?.(formattedImage);
// //         } else if (eventName === 'token') {
// //           onToken?.(payload.text);
// //         } else if (eventName === 'error') {
// //           onError?.(payload.text);
// //         } else if (eventName === 'done') {
// //           onDone?.();
// //         }
// //       }
// //     }
// //   };

// //   // ── Normal text-only chat (unchanged behavior) ──
// //   const handleSendMessage = async () => {
// //     const text = input.trim();
// //     if (!text) return;

// //     appendMessage({ sender: 'user', text });
// //     setInput('');
// //     setLoading(true);
// //     appendMessage({ sender: 'bot', text: '' });

// //     let firstToken = true;
// //     try {
// //       await runChatStream(text, null, {
// //         onToken: (t) => {
// //           if (firstToken) {
// //             setLoading(false);
// //             firstToken = false;
// //           }
// //           updateLastMessage((m) => ({ ...m, text: m.text + t }));
// //         },
// //         onError: (t) => updateLastMessage((m) => ({ ...m, text: t })),
// //       });
// //     } catch (err) {
// //       updateLastMessage((m) => ({ ...m, text: '⚠️ Server error while sending message. Ensure backend is running.' }));
// //     }
// //     setLoading(false);
// //   };

// //   const handleOpenFile = () => {
// //     fileInputRef.current?.click();
// //   };

// //   // 🟢 Image selected → immediately start processing, open dialog, stream result INTO the dialog (not chat yet)
// //   const handleImageSelect = async (event) => {
// //     const file = event.target.files?.[0];
// //     if (!file) return;
// //     event.target.value = null; // reset file input

// //     const previewUrl = URL.createObjectURL(file);
// //     setDialogFileName(file.name);
// //     setDialogUserImageUrl(previewUrl);
// //     setDialogBotText('');
// //     setDialogBotImage(null);
// //     setDialogOpen(true);
// //     setDialogLoading(true);

// //     let firstToken = true;
// //     try {
// //       await runChatStream('', file, {
// //         onMeta: (imgData) => setDialogBotImage(imgData),
// //         onToken: (t) => {
// //           if (firstToken) {
// //             setDialogLoading(false);
// //             firstToken = false;
// //           }
// //           setDialogBotText((prev) => prev + t);
// //         },
// //         onError: (t) => {
// //           setDialogLoading(false);
// //           setDialogBotText((prev) => prev + t);
// //         },
// //       });
// //     } catch (err) {
// //       setDialogLoading(false);
// //       setDialogBotText((prev) => prev + '⚠️ Server error while processing image. Ensure backend is running.');
// //     }
// //     setDialogLoading(false);
// //   };

// //   // 🟢 ✕ ক্লিক → dialog বন্ধ + জমে থাকা রেজাল্ট (user image + bot response) চ্যাট হিস্টোরিতে চলে যাবে
// //   const handleDialogCrossClick = () => {
// //     appendMessage({
// //       sender: 'user',
// //       text: `[Uploaded Image: ${dialogFileName}]`,
// //       imageUrl: dialogUserImageUrl
// //     });
// //     appendMessage({
// //       sender: 'bot',
// //       text: dialogBotText,
// //       image: dialogBotImage
// //     });

// //     setDialogOpen(false);
// //     setDialogFileName('');
// //     setDialogBotText('');
// //     setDialogBotImage(null);
// //     setDialogUserImageUrl(null); // note: don't revoke here since it's now used in chat history
// //   };

// //   return (
// //     <div style={{ maxWidth: '900px', margin: '0 auto', fontFamily: 'sans-serif', padding: '24px' }}>
// //       <h2 style={{ textAlign: 'center', color: '#222' }}>Polyp Segmentation & Analysis Assistant</h2>

// //       {/* Hidden File Input */}
// //       <input
// //         type="file"
// //         ref={fileInputRef}
// //         onChange={handleImageSelect}
// //         accept="image/*"
// //         style={{ display: 'none' }}
// //       />

// //       {/* 🟢 Processing Result Dialog */}
// //       {dialogOpen && (
// //         <div
// //           style={{
// //             position: 'fixed',
// //             inset: 0,
// //             backgroundColor: 'rgba(0,0,0,0.6)',
// //             display: 'flex',
// //             alignItems: 'center',
// //             justifyContent: 'center',
// //             zIndex: 1000
// //           }}
// //         >
// //           <div
// //             style={{
// //               backgroundColor: '#fff',
// //               borderRadius: '14px',
// //               padding: '20px',
// //               width: '520px',
// //               maxWidth: '90vw',
// //               maxHeight: '90vh',
// //               overflowY: 'auto',
// //               position: 'relative',
// //               boxShadow: '0 10px 30px rgba(0,0,0,0.3)'
// //             }}
// //           >
// //             {/* ✕ ক্রস বাটন — চ্যাট হিস্টোরিতে পাঠানোর ট্রিগার */}
// //             <button
// //               onClick={handleDialogCrossClick}
// //               title="বন্ধ করুন এবং চ্যাট হিস্টোরিতে পাঠান"
// //               style={{
// //                 position: 'absolute',
// //                 top: '-14px',
// //                 right: '-14px',
// //                 width: '34px',
// //                 height: '34px',
// //                 borderRadius: '50%',
// //                 border: 'none',
// //                 backgroundColor: '#d9534f',
// //                 color: '#fff',
// //                 fontSize: '18px',
// //                 fontWeight: 'bold',
// //                 cursor: 'pointer',
// //                 boxShadow: '0 2px 6px rgba(0,0,0,0.3)'
// //               }}
// //             >
// //               ✕
// //             </button>

// //             <div style={{ fontSize: '14px', fontWeight: 'bold', color: '#333', marginBottom: '10px' }}>
// //               {dialogFileName}
// //             </div>

// //             {/* Original uploaded image */}
// //             {dialogUserImageUrl && (
// //               <img
// //                 src={dialogUserImageUrl}
// //                 alt="Uploaded"
// //                 style={{ width: '100%', maxHeight: '260px', objectFit: 'contain', borderRadius: '10px', border: '1px solid #eee', marginBottom: '12px' }}
// //               />
// //             )}

// //             {dialogLoading && (
// //               <div style={{ color: '#007bff', fontStyle: 'italic', marginBottom: '10px' }}>
// //                 ⏳ Processing segmentation model & streaming response...
// //               </div>
// //             )}

// //             {/* Segmentation result image (streamed via 'meta' event) */}
// //             {dialogBotImage && (
// //               <div style={{ marginBottom: '12px' }}>
// //                 <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#666', marginBottom: '4px' }}>Segmentation Result:</div>
// //                 <img src={dialogBotImage} alt="Segmentation result" style={{ width: '100%', borderRadius: '10px', border: '1px solid #ccc' }} />
// //               </div>
// //             )}

// //             {/* Streamed bot text response */}
// //             {dialogBotText && (
// //               <div className="markdown-body" style={{ fontSize: '14px' }}>
// //                 <ReactMarkdown remarkPlugins={[remarkGfm]}>{dialogBotText}</ReactMarkdown>
// //               </div>
// //             )}

// //             <div style={{ fontSize: '12px', color: '#888', marginTop: '14px', textAlign: 'center' }}>
// //               ✕ চাপুন এই রেজাল্ট চ্যাট হিস্টোরিতে পাঠাতে
// //             </div>
// //           </div>
// //         </div>
// //       )}

// //       {/* Chat Messages Container */}
// //       <div style={{
// //         border: '1px solid #ddd',
// //         borderRadius: '12px',
// //         padding: '20px',
// //         height: '60vh',
// //         overflowY: 'auto',
// //         backgroundColor: '#fafafa'
// //       }}>
// //         {messages.map((msg, idx) => (
// //           <div key={idx} style={{ marginBottom: '18px', textAlign: msg.sender === 'user' ? 'right' : 'left' }}>
// //             <div style={{
// //               display: 'inline-block',
// //               padding: '12px 18px',
// //               borderRadius: '16px',
// //               backgroundColor: msg.sender === 'user' ? '#0b74de' : '#ffffff',
// //               color: msg.sender === 'user' ? '#fff' : '#111',
// //               boxShadow: '0 2px 5px rgba(0,0,0,0.05)',
// //               maxWidth: '85%',
// //               textAlign: 'left',
// //               border: msg.sender === 'user' ? 'none' : '1px solid #e0e0e0'
// //             }}>
// //               {msg.sender === 'bot' ? (
// //                 <div className="markdown-body">
// //                   <ReactMarkdown remarkPlugins={[remarkGfm]}>
// //                     {msg.text || ' '}
// //                   </ReactMarkdown>
// //                 </div>
// //               ) : (
// //                 <div style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</div>
// //               )}

// //               {msg.imageUrl && (
// //                 <div style={{ marginTop: '12px' }}>
// //                   <img src={msg.imageUrl} alt="Uploaded input" style={{ maxWidth: '100%', maxHeight: '300px', borderRadius: '10px', border: '1px solid #ccc' }} />
// //                 </div>
// //               )}

// //               {msg.image && (
// //                 <div style={{ marginTop: '12px' }}>
// //                   <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#666', marginBottom: '4px' }}>Segmentation Result:</div>
// //                   <img src={msg.image} alt="Segmentation result" style={{ width: '100%', borderRadius: '10px', border: '1px solid #ccc' }} />
// //                 </div>
// //               )}
// //             </div>
// //           </div>
// //         ))}
// //         {loading && <div style={{ color: '#007bff', fontStyle: 'italic', padding: '8px 0' }}>⏳ Processing segmentation model & streaming response...</div>}
// //         <div ref={messagesEndRef} />
// //       </div>

// //       {/* Bottom Control Bar */}
// //       <div style={{ display: 'flex', marginTop: '16px', gap: '10px' }}>
// //         <button
// //           type="button"
// //           onClick={handleOpenFile}
// //           disabled={loading}
// //           style={{
// //             padding: '12px 16px',
// //             backgroundColor: '#6c757d',
// //             color: '#fff',
// //             border: 'none',
// //             borderRadius: '10px',
// //             cursor: 'pointer',
// //             display: 'flex',
// //             alignItems: 'center',
// //             gap: '6px'
// //           }}
// //         >
// //           📷 Select Image
// //         </button>

// //         <input
// //           type="text"
// //           value={input}
// //           onChange={(e) => setInput(e.target.value)}
// //           onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
// //           placeholder="Type a message or prompt..."
// //           style={{ flex: 1, padding: '12px 14px', borderRadius: '10px', border: '1px solid #ccc' }}
// //         />

// //         <button
// //           onClick={handleSendMessage}
// //           disabled={!input.trim() || loading}
// //           style={{
// //             padding: '12px 24px',
// //             background: loading ? '#a0c7ff' : '#007bff',
// //             color: '#fff',
// //             border: 'none',
// //             borderRadius: '10px',
// //             fontWeight: 'bold',
// //             cursor: loading ? 'not-allowed' : 'pointer'
// //           }}
// //         >
// //           Send
// //         </button>
// //       </div>
// //     </div>
// //   );
// // }

// // export default App;


// import React, { useState, useRef, useEffect } from 'react';
// import ReactMarkdown from 'react-markdown';
// import remarkGfm from 'remark-gfm';
// import './App.css';

// const API_BASE = 'http://localhost:8000';

// // shared style for the dialog's minimize / maximize / close buttons
// const dialogControlBtnStyle = {
//   width: '30px',
//   height: '30px',
//   borderRadius: '8px',
//   border: '1px solid #ddd',
//   backgroundColor: '#f2f2f2',
//   color: '#333',
//   fontSize: '15px',
//   fontWeight: 'bold',
//   cursor: 'pointer',
//   display: 'flex',
//   alignItems: 'center',
//   justifyContent: 'center'
// };

// // helper: normalize incoming image data (raw base64 or already data:/http url) into a usable <img src>
// const formatImage = (img) => {
//   if (!img) return null;
//   if (img.startsWith('data:') || img.startsWith('http')) return img;
//   return `data:image/png;base64,${img}`;
// };

// function App() {
//   const [messages, setMessages] = useState([
//     { sender: 'bot', text: 'Hello! Ask a question or upload a polyp image for segmentation analysis.' }
//   ]);
//   const [input, setInput] = useState('');
//   const [loading, setLoading] = useState(false);
//   const fileInputRef = useRef(null);
//   const messagesEndRef = useRef(null);

//   // 🟢 Image processing dialog state
//   const [dialogOpen, setDialogOpen] = useState(false);
//   const [dialogFileName, setDialogFileName] = useState('');
//   const [dialogUserImageUrl, setDialogUserImageUrl] = useState(null); // uploaded (main) image preview
//   const [dialogMaskImage, setDialogMaskImage] = useState(null);       // predicted mask image
//   const [dialogFinalImage, setDialogFinalImage] = useState(null);     // final overlay/result image
//   const [dialogBotText, setDialogBotText] = useState('');             // streamed text — collected silently, NOT shown in dialog
//   const [dialogLoading, setDialogLoading] = useState(false);
//   const [dialogMinimized, setDialogMinimized] = useState(false);      // 🟢 collapsed to a small floating bar
//   const [dialogMaximized, setDialogMaximized] = useState(false);      // 🟢 expanded to (near) full screen

//   useEffect(() => {
//     messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
//   }, [messages, loading]);

//   useEffect(() => {
//     return () => {
//       if (dialogUserImageUrl) URL.revokeObjectURL(dialogUserImageUrl);
//     };
//   }, [dialogUserImageUrl]);

//   const appendMessage = (message) => {
//     setMessages((prev) => [...prev, message]);
//   };

//   const updateLastMessage = (updater) => {
//     setMessages((prev) => {
//       const next = [...prev];
//       const lastIdx = next.length - 1;
//       next[lastIdx] = updater(next[lastIdx]);
//       return next;
//     });
//   };

//   // ── Shared SSE stream parser: reads /chat response and fires callbacks per event ──
//   const runChatStream = async (text, file, { onMeta, onToken, onError, onDone }) => {
//     const formData = new FormData();
//     formData.append('message', text || '');
//     if (file) formData.append('file', file);

//     const response = await fetch(`${API_BASE}/chat`, {
//       method: 'POST',
//       body: formData,
//     });

//     if (!response.ok || !response.body) {
//       throw new Error('Server error while streaming response.');
//     }

//     const reader = response.body.getReader();
//     const decoder = new TextDecoder('utf-8');
//     let buffer = '';

//     while (true) {
//       const { done, value } = await reader.read();
//       if (done) break;

//       buffer += decoder.decode(value, { stream: true });

//       let boundary;
//       while ((boundary = buffer.indexOf('\n\n')) !== -1) {
//         const rawFrame = buffer.slice(0, boundary);
//         buffer = buffer.slice(boundary + 2);

//         const eventLine = rawFrame.split('\n').find((l) => l.startsWith('event: '));
//         const dataLine = rawFrame.split('\n').find((l) => l.startsWith('data: '));
//         if (!eventLine || !dataLine) continue;

//         const eventName = eventLine.replace('event: ', '').trim();
//         const payload = JSON.parse(dataLine.replace('data: ', ''));

//         if (eventName === 'meta') {
//           // 🟢 payload can now contain multiple images: mask_image, final_image
//           // (falls back to legacy single "image_data" field if backend hasn't been updated)
//           onMeta?.(payload);
//         } else if (eventName === 'token') {
//           onToken?.(payload.text);
//         } else if (eventName === 'error') {
//           onError?.(payload.text);
//         } else if (eventName === 'done') {
//           onDone?.();
//         }
//       }
//     }
//   };

//   // ── Normal text-only chat (unchanged behavior) ──
//   const handleSendMessage = async () => {
//     const text = input.trim();
//     if (!text) return;

//     appendMessage({ sender: 'user', text });
//     setInput('');
//     setLoading(true);
//     appendMessage({ sender: 'bot', text: '' });

//     let firstToken = true;
//     try {
//       await runChatStream(text, null, {
//         onToken: (t) => {
//           if (firstToken) {
//             setLoading(false);
//             firstToken = false;
//           }
//           updateLastMessage((m) => ({ ...m, text: m.text + t }));
//         },
//         onError: (t) => updateLastMessage((m) => ({ ...m, text: t })),
//       });
//     } catch (err) {
//       updateLastMessage((m) => ({ ...m, text: '⚠️ Server error while sending message. Ensure backend is running.' }));
//     }
//     setLoading(false);
//   };

//   const handleOpenFile = () => {
//     fileInputRef.current?.click();
//   };

//   // 🟢 Image selected → open dialog, stream segmentation result (mask + final) INTO the dialog as a collage.
//   // The LLM's text explanation is collected silently in the background and is
//   // only revealed once the user closes the dialog (moves the result to chat history).
//   const handleImageSelect = async (event) => {
//     const file = event.target.files?.[0];
//     if (!file) return;
//     event.target.value = null; // reset file input

//     const previewUrl = URL.createObjectURL(file);
//     setDialogFileName(file.name);
//     setDialogUserImageUrl(previewUrl);
//     setDialogMaskImage(null);
//     setDialogFinalImage(null);
//     setDialogBotText('');
//     setDialogMinimized(false);
//     setDialogMaximized(false);
//     setDialogOpen(true);
//     setDialogLoading(true);

//     try {
//       await runChatStream('', file, {
//         onMeta: (payload) => {
//           // stop showing the spinner as soon as the segmentation images arrive
//           setDialogLoading(false);

//           if (payload.mask_image) setDialogMaskImage(formatImage(payload.mask_image));
//           if (payload.final_image) setDialogFinalImage(formatImage(payload.final_image));

//           // backward compatibility: if backend still sends a single "image_data"
//           // field (old format), treat it as the final result image.
//           if (payload.image_data && !payload.mask_image && !payload.final_image) {
//             setDialogFinalImage(formatImage(payload.image_data));
//           }
//         },
//         onToken: (t) => {
//           // collected silently — intentionally not rendered while dialog is open
//           setDialogBotText((prev) => prev + t);
//         },
//         onError: (t) => {
//           setDialogLoading(false);
//           setDialogBotText((prev) => prev + t);
//         },
//       });
//     } catch (err) {
//       setDialogLoading(false);
//       setDialogBotText((prev) => prev + '⚠️ Server error while processing image. Ensure backend is running.');
//     }
//     setDialogLoading(false);
//   };

//   // 🟢 ✕ ক্লিক → dialog বন্ধ + জমে থাকা রেজাল্ট (main image + mask + final + LLM টেক্সট) চ্যাট হিস্টোরিতে চলে যাবে
//   const handleDialogCrossClick = () => {
//     appendMessage({
//       sender: 'user',
//       text: `[Uploaded Image: ${dialogFileName}]`,
//       imageUrl: dialogUserImageUrl
//     });
//     appendMessage({
//       sender: 'bot',
//       text: dialogBotText,
//       images: {
//         main: dialogUserImageUrl,
//         mask: dialogMaskImage,
//         final: dialogFinalImage
//       }
//     });

//     setDialogOpen(false);
//     setDialogMinimized(false);
//     setDialogMaximized(false);
//     setDialogFileName('');
//     setDialogBotText('');
//     setDialogMaskImage(null);
//     setDialogFinalImage(null);
//     setDialogUserImageUrl(null); // note: don't revoke here since it's now used in chat history
//   };

//   // 🟢 reusable collage renderer: main / predicted mask / final result, side by side
//   const renderCollage = (main, mask, final, imgHeight = '150px') => {
//     const items = [
//       { label: 'Main Image', src: main },
//       { label: 'Segmented Mask', src: mask },
//       { label: 'Occlusion Overlay', src: final },
//     ].filter((it) => it.src);

//     if (items.length === 0) return null;

//     return (
//       <div style={{ display: 'flex', gap: '10px', marginTop: '10px', marginBottom: '10px', flexWrap: 'wrap' }}>
//         {items.map((it) => (
//           <div key={it.label} style={{ flex: '1 1 0', minWidth: '120px' }}>
//             <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#666', marginBottom: '4px', textAlign: 'center' }}>
//               {it.label}
//             </div>
//             <img
//               src={it.src}
//               alt={it.label}
//               style={{
//                 width: '100%',
//                 height: imgHeight,
//                 objectFit: 'contain',
//                 borderRadius: '10px',
//                 border: '1px solid #ccc',
//                 backgroundColor: '#fff'
//               }}
//             />
//           </div>
//         ))}
//       </div>
//     );
//   };

//   return (
//     <div style={{ maxWidth: '900px', margin: '0 auto', fontFamily: 'sans-serif', padding: '24px' }}>
//       <h2 style={{ textAlign: 'center', color: '#222' }}>Polyp Segmentation & Analysis Assistant</h2>

//       {/* Hidden File Input */}
//       <input
//         type="file"
//         ref={fileInputRef}
//         onChange={handleImageSelect}
//         accept="image/*"
//         style={{ display: 'none' }}
//       />

//       {/* 🟢 Minimized floating bar (click to restore) */}
//       {dialogOpen && dialogMinimized && (
//         <div
//           onClick={() => setDialogMinimized(false)}
//           title="Restore"
//           style={{
//             position: 'fixed',
//             bottom: '20px',
//             right: '20px',
//             zIndex: 1000,
//             backgroundColor: '#fff',
//             borderRadius: '12px',
//             padding: '12px 16px',
//             boxShadow: '0 6px 20px rgba(0,0,0,0.25)',
//             border: '1px solid #ddd',
//             display: 'flex',
//             alignItems: 'center',
//             gap: '10px',
//             cursor: 'pointer',
//             maxWidth: '260px'
//           }}
//         >
//           {dialogUserImageUrl && (
//             <img src={dialogUserImageUrl} alt="thumb" style={{ width: '36px', height: '36px', objectFit: 'cover', borderRadius: '6px' }} />
//           )}
//           <div style={{ fontSize: '13px', color: '#333', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
//             {dialogLoading ? '⏳ Processing...' : (dialogFileName || 'Result')}
//           </div>
//         </div>
//       )}

//       {/* 🟢 Processing Result Dialog */}
//       {dialogOpen && !dialogMinimized && (
//         <div
//           style={{
//             position: 'fixed',
//             inset: 0,
//             backgroundColor: 'rgba(0,0,0,0.6)',
//             display: 'flex',
//             alignItems: 'center',
//             justifyContent: 'center',
//             zIndex: 1000
//           }}
//         >
//           <div
//             style={{
//               backgroundColor: '#fff',
//               borderRadius: '14px',
//               padding: '20px',
//               width: dialogMaximized ? '95vw' : '700px',
//               maxWidth: '95vw',
//               height: dialogMaximized ? '92vh' : 'auto',
//               maxHeight: '92vh',
//               overflowY: 'auto',
//               position: 'relative',
//               boxShadow: '0 10px 30px rgba(0,0,0,0.3)'
//             }}
//           >
//             {/* Header: filename + minimize / maximize / close controls */}
//             <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px', gap: '8px' }}>
//               <div style={{ fontSize: '14px', fontWeight: 'bold', color: '#333', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
//                 {dialogFileName}
//               </div>
//               <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
//                 <button
//                   onClick={() => setDialogMinimized(true)}
//                   title="Minimize"
//                   style={dialogControlBtnStyle}
//                 >
//                   &#8211;
//                 </button>
//                 <button
//                   onClick={() => setDialogMaximized((v) => !v)}
//                   title={dialogMaximized ? 'Restore' : 'Maximize'}
//                   style={dialogControlBtnStyle}
//                 >
//                   {dialogMaximized ? '🗗' : '⛶'}
//                 </button>
//                 <button
//                   onClick={handleDialogCrossClick}
//                   title="বন্ধ করুন এবং চ্যাট হিস্টোরিতে পাঠান"
//                   style={{ ...dialogControlBtnStyle, backgroundColor: '#d9534f', color: '#fff' }}
//                 >
//                   ✕
//                 </button>
//               </div>
//             </div>

//             {dialogLoading && (
//               <div style={{ color: '#007bff', fontStyle: 'italic', marginBottom: '10px' }}>
//                 ⏳ Processing segmentation model & streaming response...
//               </div>
//             )}

//             {/* 🟢 Collage: main image / segmented mask / occlusion overlay side by side */}
//             {renderCollage(dialogUserImageUrl, dialogMaskImage, dialogFinalImage, dialogMaximized ? '320px' : '180px')}

//             {/* Note: LLM এর টেক্সট রেসপন্স এখানে দেখানো হয় না — ✕ চাপার পরই চ্যাটে দেখা যাবে */}
//             {!dialogLoading && (dialogMaskImage || dialogFinalImage) && (
//               <div style={{ fontSize: '13px', color: '#888', marginTop: '6px', textAlign: 'center' }}>
//                 বিশ্লেষণ সম্পন্ন হচ্ছে। বিস্তারিত ব্যাখ্যা দেখতে নিচের ✕ চাপুন।
//               </div>
//             )}

//             <div style={{ fontSize: '12px', color: '#888', marginTop: '14px', textAlign: 'center' }}>
//               ✕ চাপুন এই রেজাল্ট চ্যাট হিস্টোরিতে পাঠাতে
//             </div>
//           </div>
//         </div>
//       )}

//       {/* Chat Messages Container */}
//       <div style={{
//         border: '1px solid #ddd',
//         borderRadius: '12px',
//         padding: '20px',
//         height: '60vh',
//         overflowY: 'auto',
//         backgroundColor: '#fafafa'
//       }}>
//         {messages.map((msg, idx) => (
//           <div key={idx} style={{ marginBottom: '18px', textAlign: msg.sender === 'user' ? 'right' : 'left' }}>
//             <div style={{
//               display: 'inline-block',
//               padding: '12px 18px',
//               borderRadius: '16px',
//               backgroundColor: msg.sender === 'user' ? '#0b74de' : '#ffffff',
//               color: msg.sender === 'user' ? '#fff' : '#111',
//               boxShadow: '0 2px 5px rgba(0,0,0,0.05)',
//               maxWidth: msg.images ? '95%' : '85%',
//               textAlign: 'left',
//               border: msg.sender === 'user' ? 'none' : '1px solid #e0e0e0'
//             }}>
//               {msg.sender === 'bot' ? (
//                 <div className="markdown-body">
//                   <ReactMarkdown remarkPlugins={[remarkGfm]}>
//                     {msg.text || ' '}
//                   </ReactMarkdown>
//                 </div>
//               ) : (
//                 <div style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</div>
//               )}

//               {msg.imageUrl && (
//                 <div style={{ marginTop: '12px' }}>
//                   <img src={msg.imageUrl} alt="Uploaded input" style={{ maxWidth: '100%', maxHeight: '300px', borderRadius: '10px', border: '1px solid #ccc' }} />
//                 </div>
//               )}

//               {/* 🟢 collage rendered in chat history once dialog is closed */}
//               {msg.images && renderCollage(msg.images.main, msg.images.mask, msg.images.final, '160px')}
//             </div>
//           </div>
//         ))}
//         {loading && <div style={{ color: '#007bff', fontStyle: 'italic', padding: '8px 0' }}>⏳ Processing segmentation model & streaming response...</div>}
//         <div ref={messagesEndRef} />
//       </div>

//       {/* Bottom Control Bar */}
//       <div style={{ display: 'flex', marginTop: '16px', gap: '10px' }}>
//         <button
//           type="button"
//           onClick={handleOpenFile}
//           disabled={loading}
//           style={{
//             padding: '12px 16px',
//             backgroundColor: '#6c757d',
//             color: '#fff',
//             border: 'none',
//             borderRadius: '10px',
//             cursor: 'pointer',
//             display: 'flex',
//             alignItems: 'center',
//             gap: '6px'
//           }}
//         >
//           📷 Select Image
//         </button>

//         <input
//           type="text"
//           value={input}
//           onChange={(e) => setInput(e.target.value)}
//           onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
//           placeholder="Type a message or prompt..."
//           style={{ flex: 1, padding: '12px 14px', borderRadius: '10px', border: '1px solid #ccc' }}
//         />

//         <button
//           onClick={handleSendMessage}
//           disabled={!input.trim() || loading}
//           style={{
//             padding: '12px 24px',
//             background: loading ? '#a0c7ff' : '#007bff',
//             color: '#fff',
//             border: 'none',
//             borderRadius: '10px',
//             fontWeight: 'bold',
//             cursor: loading ? 'not-allowed' : 'pointer'
//           }}
//         >
//           Send
//         </button>
//       </div>
//     </div>
//   );
// }

// export default App;

// import React, { useState, useRef, useEffect } from 'react';
// import ReactMarkdown from 'react-markdown';
// import remarkGfm from 'remark-gfm';
// import './App.css';

// const API_BASE = 'http://localhost:8000';

// // shared style for the dialog's minimize / maximize / close buttons
// const dialogControlBtnStyle = {
//   width: '30px',
//   height: '30px',
//   borderRadius: '8px',
//   border: '1px solid #ddd',
//   backgroundColor: '#f2f2f2',
//   color: '#333',
//   fontSize: '15px',
//   fontWeight: 'bold',
//   cursor: 'pointer',
//   display: 'flex',
//   alignItems: 'center',
//   justifyContent: 'center'
// };

// // helper: normalize incoming image data (raw base64 or already data:/http url) into a usable <img src>
// const formatImage = (img) => {
//   if (!img) return null;
//   if (img.startsWith('data:') || img.startsWith('http')) return img;
//   return `data:image/png;base64,${img}`;
// };

// function App() {
//   const [messages, setMessages] = useState([
//     { sender: 'bot', text: 'Hello! Ask a question or upload a polyp image for segmentation analysis.' }
//   ]);
//   const [input, setInput] = useState('');
//   const [loading, setLoading] = useState(false);
//   const fileInputRef = useRef(null);
//   const messagesEndRef = useRef(null);

//   // 🟢 STAGED image (uploaded but not yet submitted — attached to the input bar, waiting for a prompt)
//   const [pendingImage, setPendingImage] = useState(null);
//   const [pendingImageUrl, setPendingImageUrl] = useState(null);

//   // 🟢 Image processing dialog state (opens only after Send is pressed)
//   const [dialogOpen, setDialogOpen] = useState(false);
//   const [dialogFileName, setDialogFileName] = useState('');
//   const [dialogUserImageUrl, setDialogUserImageUrl] = useState(null); // uploaded (main) image preview
//   const [dialogMaskImage, setDialogMaskImage] = useState(null);       // predicted mask image
//   const [dialogFinalImage, setDialogFinalImage] = useState(null);     // final overlay/result image
//   const [dialogBotText, setDialogBotText] = useState('');             // streamed text — collected silently, NOT shown in dialog
//   const [dialogLoading, setDialogLoading] = useState(false);
//   const [dialogMinimized, setDialogMinimized] = useState(false);      // collapsed to a small floating bar
//   const [dialogMaximized, setDialogMaximized] = useState(false);      // expanded to (near) full screen

//   useEffect(() => {
//     messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
//   }, [messages, loading]);

//   useEffect(() => {
//     return () => {
//       if (pendingImageUrl) URL.revokeObjectURL(pendingImageUrl);
//     };
//   }, [pendingImageUrl]);

//   const appendMessage = (message) => {
//     setMessages((prev) => [...prev, message]);
//   };

//   const updateLastMessage = (updater) => {
//     setMessages((prev) => {
//       const next = [...prev];
//       const lastIdx = next.length - 1;
//       next[lastIdx] = updater(next[lastIdx]);
//       return next;
//     });
//   };

//   // ── Shared SSE stream parser: reads /chat response and fires callbacks per event ──
//   const runChatStream = async (text, file, { onMeta, onToken, onError, onDone }) => {
//     const formData = new FormData();
//     formData.append('message', text || '');
//     if (file) formData.append('file', file);

//     const response = await fetch(`${API_BASE}/chat`, {
//       method: 'POST',
//       body: formData,
//     });

//     if (!response.ok || !response.body) {
//       throw new Error('Server error while streaming response.');
//     }

//     const reader = response.body.getReader();
//     const decoder = new TextDecoder('utf-8');
//     let buffer = '';

//     while (true) {
//       const { done, value } = await reader.read();
//       if (done) break;

//       buffer += decoder.decode(value, { stream: true });

//       let boundary;
//       while ((boundary = buffer.indexOf('\n\n')) !== -1) {
//         const rawFrame = buffer.slice(0, boundary);
//         buffer = buffer.slice(boundary + 2);

//         const eventLine = rawFrame.split('\n').find((l) => l.startsWith('event: '));
//         const dataLine = rawFrame.split('\n').find((l) => l.startsWith('data: '));
//         if (!eventLine || !dataLine) continue;

//         const eventName = eventLine.replace('event: ', '').trim();
//         const payload = JSON.parse(dataLine.replace('data: ', ''));

//         if (eventName === 'meta') {
//           // payload can contain multiple images: mask_image, final_image
//           // (falls back to legacy single "image_data" field if backend hasn't been updated)
//           onMeta?.(payload);
//         } else if (eventName === 'token') {
//           onToken?.(payload.text);
//         } else if (eventName === 'error') {
//           onError?.(payload.text);
//         } else if (eventName === 'done') {
//           onDone?.();
//         }
//       }
//     }
//   };

//   // ── Text-only chat (no pending image attached) ──
//   const runTextOnlyChat = async (text) => {
//     appendMessage({ sender: 'user', text });
//     setLoading(true);
//     appendMessage({ sender: 'bot', text: '' });

//     let firstToken = true;
//     try {
//       await runChatStream(text, null, {
//         onToken: (t) => {
//           if (firstToken) {
//             setLoading(false);
//             firstToken = false;
//           }
//           updateLastMessage((m) => ({ ...m, text: m.text + t }));
//         },
//         onError: (t) => updateLastMessage((m) => ({ ...m, text: t })),
//       });
//     } catch (err) {
//       updateLastMessage((m) => ({ ...m, text: '⚠️ Server error while sending message. Ensure backend is running.' }));
//     }
//     setLoading(false);
//   };

//   // ── Image + prompt chat (opens dialog, streams collage into it) ──
//   const runImagePromptChat = async (text, file, previewUrl, fileName) => {
//     setDialogFileName(fileName);
//     setDialogUserImageUrl(previewUrl);
//     setDialogMaskImage(null);
//     setDialogFinalImage(null);
//     setDialogBotText('');
//     setDialogMinimized(false);
//     setDialogMaximized(false);
//     setDialogOpen(true);
//     setDialogLoading(true);

//     try {
//       await runChatStream(text, file, {
//         onMeta: (payload) => {
//           setDialogLoading(false);

//           if (payload.mask_image) setDialogMaskImage(formatImage(payload.mask_image));
//           if (payload.final_image) setDialogFinalImage(formatImage(payload.final_image));

//           // backward compatibility: single "image_data" field (old format) → treat as final result
//           if (payload.image_data && !payload.mask_image && !payload.final_image) {
//             setDialogFinalImage(formatImage(payload.image_data));
//           }
//         },
//         onToken: (t) => {
//           // collected silently — intentionally not rendered while dialog is open
//           setDialogBotText((prev) => prev + t);
//         },
//         onError: (t) => {
//           setDialogLoading(false);
//           setDialogBotText((prev) => prev + t);
//         },
//       });
//     } catch (err) {
//       setDialogLoading(false);
//       setDialogBotText((prev) => prev + '⚠️ Server error while processing image. Ensure backend is running.');
//     }
//     setDialogLoading(false);
//   };

//   // 🟢 Send button / Enter → branches based on whether an image is currently staged
//   const handleSendMessage = async () => {
//     const text = input.trim();
//     const fileToSend = pendingImage;
//     const fileUrlToSend = pendingImageUrl;
//     const fileName = pendingImage?.name || '';

//     if (!text && !fileToSend) return;

//     // Clear the input bar immediately
//     setInput('');
//     setPendingImage(null);
//     setPendingImageUrl(null);

//     if (fileToSend) {
//       // Image was attached → go through the processing dialog flow
//       await runImagePromptChat(text, fileToSend, fileUrlToSend, fileName);
//     } else {
//       // Plain text → normal chat flow
//       await runTextOnlyChat(text);
//     }
//   };

//   const handleOpenFile = () => {
//     fileInputRef.current?.click();
//   };

//   // 🟢 Image selected → ONLY stage/attach it, do NOT process yet. User still needs to type a prompt and press Send.
//   const handleImageSelect = (event) => {
//     const file = event.target.files?.[0];
//     if (!file) return;

//     if (pendingImageUrl) URL.revokeObjectURL(pendingImageUrl);
//     const previewUrl = URL.createObjectURL(file);

//     setPendingImage(file);
//     setPendingImageUrl(previewUrl);
//     event.target.value = null; // reset file input
//   };

//   const handleRemovePendingImage = () => {
//     if (pendingImageUrl) URL.revokeObjectURL(pendingImageUrl);
//     setPendingImage(null);
//     setPendingImageUrl(null);
//   };

//   // 🟢 ✕ ক্লিক → dialog বন্ধ + জমে থাকা রেজাল্ট (main image + mask + final + LLM টেক্সট) চ্যাট হিস্টোরিতে চলে যাবে
//   const handleDialogCrossClick = () => {
//     appendMessage({
//       sender: 'user',
//       text: `[Uploaded Image: ${dialogFileName}]`,
//       imageUrl: dialogUserImageUrl
//     });
//     appendMessage({
//       sender: 'bot',
//       text: dialogBotText,
//       images: {
//         main: dialogUserImageUrl,
//         mask: dialogMaskImage,
//         final: dialogFinalImage
//       }
//     });

//     setDialogOpen(false);
//     setDialogMinimized(false);
//     setDialogMaximized(false);
//     setDialogFileName('');
//     setDialogBotText('');
//     setDialogMaskImage(null);
//     setDialogFinalImage(null);
//     setDialogUserImageUrl(null); // note: don't revoke here since it's now used in chat history
//   };

//   // 🟢 reusable collage renderer: main / predicted mask / final result, side by side
//   const renderCollage = (main, mask, final, imgHeight = '150px') => {
//     const items = [
//       { label: 'Main Image', src: main },
//       { label: 'Segmented Mask', src: mask },
//       { label: 'Occlusion Overlay', src: final },
//     ].filter((it) => it.src);

//     if (items.length === 0) return null;

//     return (
//       <div style={{ display: 'flex', gap: '10px', marginTop: '10px', marginBottom: '10px', flexWrap: 'wrap' }}>
//         {items.map((it) => (
//           <div key={it.label} style={{ flex: '1 1 0', minWidth: '120px' }}>
//             <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#666', marginBottom: '4px', textAlign: 'center' }}>
//               {it.label}
//             </div>
//             <img
//               src={it.src}
//               alt={it.label}
//               style={{
//                 width: '100%',
//                 height: imgHeight,
//                 objectFit: 'contain',
//                 borderRadius: '10px',
//                 border: '1px solid #ccc',
//                 backgroundColor: '#fff'
//               }}
//             />
//           </div>
//         ))}
//       </div>
//     );
//   };

//   const hasPending = Boolean(pendingImage);

//   return (
//     <div style={{ maxWidth: '900px', margin: '0 auto', fontFamily: 'sans-serif', padding: '24px' }}>
//       <h2 style={{ textAlign: 'center', color: '#222' }}>Polyp Segmentation & Analysis Assistant</h2>

//       {/* Hidden File Input */}
//       <input
//         type="file"
//         ref={fileInputRef}
//         onChange={handleImageSelect}
//         accept="image/*"
//         style={{ display: 'none' }}
//       />

//       {/* 🟢 Minimized floating bar (click to restore) */}
//       {dialogOpen && dialogMinimized && (
//         <div
//           onClick={() => setDialogMinimized(false)}
//           title="Restore"
//           style={{
//             position: 'fixed',
//             bottom: '20px',
//             right: '20px',
//             zIndex: 1000,
//             backgroundColor: '#fff',
//             borderRadius: '12px',
//             padding: '12px 16px',
//             boxShadow: '0 6px 20px rgba(0,0,0,0.25)',
//             border: '1px solid #ddd',
//             display: 'flex',
//             alignItems: 'center',
//             gap: '10px',
//             cursor: 'pointer',
//             maxWidth: '260px'
//           }}
//         >
//           {dialogUserImageUrl && (
//             <img src={dialogUserImageUrl} alt="thumb" style={{ width: '36px', height: '36px', objectFit: 'cover', borderRadius: '6px' }} />
//           )}
//           <div style={{ fontSize: '13px', color: '#333', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
//             {dialogLoading ? '⏳ Processing...' : (dialogFileName || 'Result')}
//           </div>
//         </div>
//       )}

//       {/* 🟢 Processing Result Dialog */}
//       {dialogOpen && !dialogMinimized && (
//         <div
//           style={{
//             position: 'fixed',
//             inset: 0,
//             backgroundColor: 'rgba(0,0,0,0.6)',
//             display: 'flex',
//             alignItems: 'center',
//             justifyContent: 'center',
//             zIndex: 1000
//           }}
//         >
//           <div
//             style={{
//               backgroundColor: '#fff',
//               borderRadius: '14px',
//               padding: '20px',
//               width: dialogMaximized ? '95vw' : '700px',
//               maxWidth: '95vw',
//               height: dialogMaximized ? '92vh' : 'auto',
//               maxHeight: '92vh',
//               overflowY: 'auto',
//               position: 'relative',
//               boxShadow: '0 10px 30px rgba(0,0,0,0.3)'
//             }}
//           >
//             {/* Header: filename + minimize / maximize / close controls */}
//             <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px', gap: '8px' }}>
//               <div style={{ fontSize: '14px', fontWeight: 'bold', color: '#333', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
//                 {dialogFileName}
//               </div>
//               <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
//                 <button onClick={() => setDialogMinimized(true)} title="Minimize" style={dialogControlBtnStyle}>
//                   &#8211;
//                 </button>
//                 <button
//                   onClick={() => setDialogMaximized((v) => !v)}
//                   title={dialogMaximized ? 'Restore' : 'Maximize'}
//                   style={dialogControlBtnStyle}
//                 >
//                   {dialogMaximized ? '🗗' : '⛶'}
//                 </button>
//                 <button
//                   onClick={handleDialogCrossClick}
//                   title="বন্ধ করুন এবং চ্যাট হিস্টোরিতে পাঠান"
//                   style={{ ...dialogControlBtnStyle, backgroundColor: '#d9534f', color: '#fff' }}
//                 >
//                   ✕
//                 </button>
//               </div>
//             </div>

//             {dialogLoading && (
//               <div style={{ color: '#007bff', fontStyle: 'italic', marginBottom: '10px' }}>
//                 ⏳ Processing segmentation model & streaming response...
//               </div>
//             )}

//             {/* Collage: main image / segmented mask / occlusion overlay side by side */}
//             {renderCollage(dialogUserImageUrl, dialogMaskImage, dialogFinalImage, dialogMaximized ? '320px' : '180px')}

//             {/* Note: LLM এর টেক্সট রেসপন্স এখানে দেখানো হয় না — ✕ চাপার পরই চ্যাটে দেখা যাবে */}
//             {!dialogLoading && (dialogMaskImage || dialogFinalImage) && (
//               <div style={{ fontSize: '13px', color: '#888', marginTop: '6px', textAlign: 'center' }}>
//                 বিশ্লেষণ সম্পন্ন হচ্ছে। বিস্তারিত ব্যাখ্যা দেখতে নিচের ✕ চাপুন।
//               </div>
//             )}

//             <div style={{ fontSize: '12px', color: '#888', marginTop: '14px', textAlign: 'center' }}>
//               ✕ চাপুন এই রেজাল্ট চ্যাট হিস্টোরিতে পাঠাতে
//             </div>
//           </div>
//         </div>
//       )}

//       {/* Chat Messages Container */}
//       <div style={{
//         border: '1px solid #ddd',
//         borderRadius: '12px',
//         padding: '20px',
//         height: '60vh',
//         overflowY: 'auto',
//         backgroundColor: '#fafafa'
//       }}>
//         {messages.map((msg, idx) => (
//           <div key={idx} style={{ marginBottom: '18px', textAlign: msg.sender === 'user' ? 'right' : 'left' }}>
//             <div style={{
//               display: 'inline-block',
//               padding: '12px 18px',
//               borderRadius: '16px',
//               backgroundColor: msg.sender === 'user' ? '#0b74de' : '#ffffff',
//               color: msg.sender === 'user' ? '#fff' : '#111',
//               boxShadow: '0 2px 5px rgba(0,0,0,0.05)',
//               maxWidth: msg.images ? '95%' : '85%',
//               textAlign: 'left',
//               border: msg.sender === 'user' ? 'none' : '1px solid #e0e0e0'
//             }}>
//               {msg.sender === 'bot' ? (
//                 <div className="markdown-body">
//                   <ReactMarkdown remarkPlugins={[remarkGfm]}>
//                     {msg.text || ' '}
//                   </ReactMarkdown>
//                 </div>
//               ) : (
//                 <div style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</div>
//               )}

//               {msg.imageUrl && (
//                 <div style={{ marginTop: '12px' }}>
//                   <img src={msg.imageUrl} alt="Uploaded input" style={{ maxWidth: '100%', maxHeight: '300px', borderRadius: '10px', border: '1px solid #ccc' }} />
//                 </div>
//               )}

//               {/* collage rendered in chat history once dialog is closed */}
//               {msg.images && renderCollage(msg.images.main, msg.images.mask, msg.images.final, '160px')}
//             </div>
//           </div>
//         ))}
//         {loading && <div style={{ color: '#007bff', fontStyle: 'italic', padding: '8px 0' }}>⏳ Processing segmentation model & streaming response...</div>}
//         <div ref={messagesEndRef} />
//       </div>

//       {/* 🟢 Pending Attached Image Preview Bar — shown after selecting an image, before Send */}
//       {pendingImageUrl && (
//         <div style={{
//           display: 'flex',
//           alignItems: 'center',
//           gap: '12px',
//           marginTop: '12px',
//           padding: '8px 12px',
//           backgroundColor: '#eef6ff',
//           borderRadius: '8px',
//           border: '1px solid #b6d4fe'
//         }}>
//           <img src={pendingImageUrl} alt="Pending preview" style={{ width: '48px', height: '48px', objectFit: 'cover', borderRadius: '6px' }} />
//           <span style={{ flex: 1, fontSize: '14px', color: '#333' }}>
//             Ready to analyze: <strong>{pendingImage?.name}</strong> — এখন প্রম্পট লিখে Send চাপুন
//           </span>
//           <button
//             onClick={handleRemovePendingImage}
//             style={{ border: 'none', background: 'transparent', color: '#d9534f', fontSize: '18px', cursor: 'pointer' }}
//           >
//             ✕
//           </button>
//         </div>
//       )}

//       {/* Bottom Control Bar */}
//       <div style={{ display: 'flex', marginTop: '16px', gap: '10px' }}>
//         <button
//           type="button"
//           onClick={handleOpenFile}
//           disabled={loading}
//           style={{
//             padding: '12px 16px',
//             backgroundColor: '#6c757d',
//             color: '#fff',
//             border: 'none',
//             borderRadius: '10px',
//             cursor: 'pointer',
//             display: 'flex',
//             alignItems: 'center',
//             gap: '6px'
//           }}
//         >
//           📷 Select Image
//         </button>

//         <input
//           type="text"
//           value={input}
//           onChange={(e) => setInput(e.target.value)}
//           onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
//           placeholder={hasPending ? "e.g. 'run score-cam on this image'..." : "Type a message or prompt..."}
//           style={{ flex: 1, padding: '12px 14px', borderRadius: '10px', border: '1px solid #ccc' }}
//         />

//         <button
//           onClick={handleSendMessage}
//           disabled={(!input.trim() && !hasPending) || loading}
//           style={{
//             padding: '12px 24px',
//             background: loading ? '#a0c7ff' : '#007bff',
//             color: '#fff',
//             border: 'none',
//             borderRadius: '10px',
//             fontWeight: 'bold',
//             cursor: loading ? 'not-allowed' : 'pointer'
//           }}
//         >
//           Send
//         </button>
//       </div>
//     </div>
//   );
// }

// export default App;
