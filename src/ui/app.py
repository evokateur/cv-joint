import gradio as gr
from services.agency_service import AgencyService
from services.knowledge_chat import KnowledgeChatService
from config.settings import get_chat_config, is_mcp_configured


def create_app():
    """Create and configure the Gradio application."""

    service = AgencyService()
    chat_config = get_chat_config()
    mcp_available = is_mcp_configured("rag-knowledge")
    chat_service = KnowledgeChatService() if mcp_available else None

    with gr.Blocks(title="CV Agents") as app:
        gr.Markdown("# CV Agency - AI/RAG powered job posting and CV analysis\n")

        with gr.Tabs():
            # Tab 1: Job Postings
            with gr.Tab("Job Postings"):
                with gr.Group():
                    gr.Markdown("### Create New Job Posting")
                    job_url = gr.Textbox(
                        label="Job Posting URL",
                        placeholder="https://...",
                    )
                    analyze_job_btn = gr.Button(
                        "Analyze Job Posting", variant="primary"
                    )

                with gr.Group():
                    gr.Markdown("### Results")
                    job_result = gr.JSON(label="Job Posting Details")
                    job_is_saved = gr.State(value=False)

                    with gr.Group(visible=False) as job_save_controls:
                        job_identifier = gr.Textbox(
                            label="Save As",
                            placeholder="company-position",
                        )
                        save_job_btn = gr.Button("Save Job Posting")
                        save_job_status = gr.Textbox(label="Status", interactive=False)

                with gr.Group():
                    gr.Markdown("### Saved Job Postings")
                    gr.Markdown("Click a row to view details")
                    job_list = gr.Dataframe(
                        headers=["Date", "Company", "Position", "URL", "Identifier"],
                        label="All Job Postings",
                        interactive=False,
                        column_widths=["10%", "15%", "20%", "35%", "20%"],
                    )
                    refresh_jobs_btn = gr.Button("Refresh List")

                # Event handlers for Job Postings tab
                def analyze_job(url):
                    if not url:
                        return (
                            None,
                            "",
                            False,
                            gr.update(visible=False),
                            "⚠ Please enter a URL",
                        )

                    job_data, identifier = service.create_job_posting(url)
                    is_saved = False
                    return (
                        job_data,
                        identifier,
                        is_saved,
                        gr.update(visible=True),
                        "✓ Analysis complete",
                    )

                def view_saved_job(evt: gr.SelectData):
                    identifier = evt.row_value[4]  # Last column is identifier

                    if not identifier:
                        return None, "", "", True, gr.update(visible=False), ""

                    job_posting = service.repository.get_job_posting(identifier)
                    if not job_posting:
                        return (
                            None,
                            "",
                            "",
                            True,
                            gr.update(visible=False),
                            f"⚠ Job posting not found",
                        )

                    job_data = job_posting.model_dump()
                    is_saved = True

                    return (
                        job_data,
                        "",
                        identifier,
                        is_saved,
                        gr.update(visible=False),
                        f"✓ Loaded: {identifier}",
                    )

                def save_job(job_data, identifier, is_saved):
                    if is_saved:
                        return (
                            "ℹ Job posting is already saved",
                            "",
                            None,
                            True,
                            gr.update(visible=False),
                        )

                    if not job_data or not identifier:
                        return (
                            "⚠ Please analyze a job posting first and provide an identifier",
                            "",
                            None,
                            False,
                            gr.update(visible=True),
                        )

                    try:
                        metadata = service.save_job_posting(job_data, identifier)
                        jobs = service.get_job_postings()
                        job_list_data = [
                            [
                                j.get("created_at", "")[:10]
                                if j.get("created_at")
                                else "",  # Just the date part
                                j.get("company", ""),
                                j.get("title", ""),
                                j.get("url", ""),
                                j.get("identifier", ""),
                            ]
                            for j in jobs
                        ]
                        return (
                            f"✓ Job posting saved: {metadata['identifier']}",
                            "",
                            job_list_data,
                            True,
                            gr.update(visible=False),
                        )
                    except Exception as e:
                        return (
                            f"✗ Error saving job posting: {str(e)}",
                            "",
                            None,
                            False,
                            gr.update(visible=True),
                        )

                def load_jobs():
                    jobs = service.get_job_postings()
                    job_list_data = [
                        [
                            j.get("created_at", "")[:10]
                            if j.get("created_at")
                            else "",  # Just the date part
                            j.get("company", ""),
                            j.get("title", ""),
                            j.get("url", ""),
                            j.get("identifier", ""),
                        ]
                        for j in jobs
                    ]
                    return job_list_data

                # Analyze job posting - clear previous results first, then run analysis
                analyze_job_btn.click(
                    fn=lambda: (
                        None,
                        "",
                        False,
                        gr.update(visible=False),
                        "⏳ Analyzing job posting...",
                    ),
                    outputs=[
                        job_result,
                        job_identifier,
                        job_is_saved,
                        job_save_controls,
                        save_job_status,
                    ],
                ).then(
                    fn=analyze_job,
                    inputs=[job_url],
                    outputs=[
                        job_result,
                        job_identifier,
                        job_is_saved,
                        job_save_controls,
                        save_job_status,
                    ],
                )

                job_list.select(
                    fn=view_saved_job,
                    outputs=[
                        job_result,
                        job_url,
                        job_identifier,
                        job_is_saved,
                        job_save_controls,
                        save_job_status,
                    ],
                )

                save_job_btn.click(
                    fn=save_job,
                    inputs=[job_result, job_identifier, job_is_saved],
                    outputs=[
                        save_job_status,
                        job_url,
                        job_list,
                        job_is_saved,
                        job_save_controls,
                    ],
                )

                refresh_jobs_btn.click(fn=load_jobs, outputs=[job_list])

                # Load jobs on startup
                app.load(fn=load_jobs, outputs=[job_list])

            # Tab 2: Curriculum Vitae
            with gr.Tab("Curriculum Vitae"):
                with gr.Group():
                    gr.Markdown("### Import CV")
                    cv_file = gr.File(
                        label="CV File", file_types=[".json", ".yaml", ".txt"]
                    )
                    cv_path = gr.Textbox(
                        label="Or File Path",
                        placeholder="/path/to/cv.json",
                    )
                    analyze_cv_btn = gr.Button("Analyze CV", variant="primary")

                with gr.Group():
                    gr.Markdown("### Results")
                    cv_result = gr.JSON(label="CV Details")
                    cv_is_saved = gr.State(value=False)

                    with gr.Group(visible=False) as cv_save_controls:
                        cv_identifier = gr.Textbox(
                            label="Save As",
                            placeholder="name",
                        )
                        save_cv_btn = gr.Button("Save CV")
                        save_cv_status = gr.Textbox(label="Status", interactive=False)

                with gr.Group():
                    gr.Markdown("### Saved CVs")
                    gr.Markdown("Click a row to view details")
                    cv_list = gr.Dataframe(
                        headers=["Date", "Identifier", "Name", "Profession"],
                        label="All CVs",
                        interactive=False,
                        column_widths=["15%", "25%", "30%", "30%"],
                    )
                    refresh_cvs_btn = gr.Button("Refresh List")

                # Event handlers for CV tab
                def analyze_cv(file, path):
                    file_path = file.name if file else path
                    if not file_path:
                        return (
                            None,
                            "",
                            False,
                            gr.update(visible=False),
                            "⚠ Please provide a file or path",
                        )

                    cv_data, identifier = service.create_cv(file_path)
                    is_saved = False
                    return (
                        cv_data,
                        identifier,
                        is_saved,
                        gr.update(visible=True),
                        "✓ Analysis complete",
                    )

                def view_saved_cv(evt: gr.SelectData):
                    identifier = evt.row_value[
                        1
                    ]  # Second column is identifier (after Date)

                    if not identifier:
                        return None, "", True, gr.update(visible=False), ""

                    cv = service.repository.get_cv(identifier)
                    if not cv:
                        return (
                            None,
                            "",
                            True,
                            gr.update(visible=False),
                            "⚠ CV not found",
                        )

                    cv_data = cv.model_dump()
                    is_saved = True

                    return (
                        cv_data,
                        identifier,
                        is_saved,
                        gr.update(visible=False),
                        f"✓ Loaded: {identifier}",
                    )

                def save_cv(cv_data, identifier, is_saved):
                    if is_saved:
                        return (
                            "ℹ CV is already saved",
                            None,
                            True,
                            gr.update(visible=False),
                        )

                    if not cv_data or not identifier:
                        return (
                            "⚠ Please analyze a CV first and provide an identifier",
                            None,
                            False,
                            gr.update(visible=True),
                        )

                    try:
                        metadata = service.save_cv(cv_data, identifier)
                        cvs = service.get_cvs()
                        cv_list_data = [
                            [
                                c.get("created_at", "")[:10]
                                if c.get("created_at")
                                else "",
                                c.get("identifier", ""),
                                c.get("name", ""),
                                c.get("profession", ""),
                            ]
                            for c in cvs
                        ]
                        return (
                            f"✓ CV saved: {metadata['identifier']}",
                            cv_list_data,
                            True,
                            gr.update(visible=False),
                        )
                    except Exception as e:
                        return (
                            f"✗ Error saving CV: {str(e)}",
                            None,
                            False,
                            gr.update(visible=True),
                        )

                def load_cvs():
                    cvs = service.get_cvs()
                    cv_list_data = [
                        [
                            c.get("created_at", "")[:10] if c.get("created_at") else "",
                            c.get("identifier", ""),
                            c.get("name", ""),
                            c.get("profession", ""),
                        ]
                        for c in cvs
                    ]
                    return cv_list_data

                # Analyze CV - clear previous results first, then run analysis
                analyze_cv_btn.click(
                    fn=lambda: (
                        None,
                        "",
                        False,
                        gr.update(visible=False),
                        "⏳ Analyzing CV...",
                    ),
                    outputs=[
                        cv_result,
                        cv_identifier,
                        cv_is_saved,
                        cv_save_controls,
                        save_cv_status,
                    ],
                ).then(
                    fn=analyze_cv,
                    inputs=[cv_file, cv_path],
                    outputs=[
                        cv_result,
                        cv_identifier,
                        cv_is_saved,
                        cv_save_controls,
                        save_cv_status,
                    ],
                )

                cv_list.select(
                    fn=view_saved_cv,
                    outputs=[
                        cv_result,
                        cv_identifier,
                        cv_is_saved,
                        cv_save_controls,
                        save_cv_status,
                    ],
                )

                save_cv_btn.click(
                    fn=save_cv,
                    inputs=[cv_result, cv_identifier, cv_is_saved],
                    outputs=[save_cv_status, cv_list, cv_is_saved, cv_save_controls],
                )

                refresh_cvs_btn.click(fn=load_cvs, outputs=[cv_list])

                # Load CVs on startup
                app.load(fn=load_cvs, outputs=[cv_list])

            # Tab 3: Optimizations
            with gr.Tab("Optimizations"):
                with gr.Group():
                    gr.Markdown("### Create New Optimization")

                    job_dropdown = gr.Dropdown(
                        label="Select Job Posting",
                        choices=[],
                        interactive=True,
                    )
                    cv_dropdown = gr.Dropdown(
                        label="Select CV",
                        choices=[],
                        interactive=True,
                    )
                    optimize_btn = gr.Button("Optimize CV", variant="primary")

                with gr.Group():
                    gr.Markdown("### Progress")
                    optimization_status = gr.Textbox(
                        label="Status",
                        interactive=False,
                        value="Ready to optimize",
                    )

                with gr.Group():
                    gr.Markdown("### Results")
                    optimization_result = gr.JSON(label="Optimization Details")

                with gr.Group():
                    gr.Markdown("### Saved Optimizations")
                    optimization_list = gr.Dataframe(
                        headers=["Identifier", "Job Posting", "CV", "Date"],
                        label="Optimizations",
                    )
                    refresh_optimizations_btn = gr.Button("Refresh List")

                # Event handlers for Optimizations tab
                def load_job_choices():
                    jobs = service.get_job_postings()
                    return gr.Dropdown(
                        choices=[
                            (f"{j['company']} - {j['title']}", j["identifier"])
                            for j in jobs
                        ]
                    )

                def load_cv_choices():
                    cvs = service.get_cvs()
                    return gr.Dropdown(
                        choices=[
                            (f"{c['name']} ({c['profession']})", c["identifier"])
                            for c in cvs
                        ]
                    )

                def run_optimization(job_id, cv_id):
                    if not job_id or not cv_id:
                        return "⚠ Please select both a job posting and a CV", {}

                    result = service.create_optimization(job_id, cv_id)
                    status = f"✓ Optimization complete: {result.get('identifier', '')}"
                    return status, result

                def load_optimizations():
                    opts = service.get_optimizations()
                    return [
                        [
                            o.get("identifier", ""),
                            o.get("job_posting", ""),
                            o.get("cv", ""),
                            o.get("date", ""),
                        ]
                        for o in opts
                    ]

                optimize_btn.click(
                    fn=run_optimization,
                    inputs=[job_dropdown, cv_dropdown],
                    outputs=[optimization_status, optimization_result],
                )

                refresh_optimizations_btn.click(
                    fn=load_optimizations, outputs=[optimization_list]
                )

                # Load optimizations and choices on startup
                app.load(fn=load_job_choices, outputs=[job_dropdown])
                app.load(fn=load_cv_choices, outputs=[cv_dropdown])
                app.load(fn=load_optimizations, outputs=[optimization_list])

            # Tab 4: PDF Generation
            with gr.Tab("PDF Generation"):
                with gr.Group():
                    gr.Markdown("### Generate PDF")

                    optimization_dropdown = gr.Dropdown(
                        label="Select Optimization",
                        choices=[],
                        interactive=True,
                    )

                    gr.Markdown("Or upload CV JSON:")
                    cv_json_file = gr.File(label="CV JSON File", file_types=[".json"])

                    template_dropdown = gr.Dropdown(
                        label="Template",
                        choices=["cv.tex", "cover-letter.tex"],
                        value="cv.tex",
                    )

                    generate_pdf_btn = gr.Button("Generate PDF", variant="primary")

                with gr.Group():
                    gr.Markdown("### Result")
                    pdf_status = gr.Textbox(label="Status", interactive=False)
                    pdf_download = gr.File(label="Download PDF", interactive=False)

                # Event handlers for PDF tab
                def load_optimization_choices():
                    opts = service.get_optimizations()
                    return gr.Dropdown(
                        choices=[
                            (f"{o['job_posting']} - {o['date']}", o["identifier"])
                            for o in opts
                        ]
                    )

                def generate_pdf(optimization_id, cv_json, template):
                    if not optimization_id and not cv_json:
                        return (
                            "⚠ Please select an optimization or upload a CV JSON",
                            None,
                        )

                    result = service.generate_pdf(optimization_id)
                    status = f"✓ PDF generated: {result.get('pdf_path', '')}"
                    # TODO: Actually return the PDF file for download
                    return status, None

                generate_pdf_btn.click(
                    fn=generate_pdf,
                    inputs=[optimization_dropdown, cv_json_file, template_dropdown],
                    outputs=[pdf_status, pdf_download],
                )

                # Load optimization choices on startup
                app.load(fn=load_optimization_choices, outputs=[optimization_dropdown])

            # Tab 5: Knowledge Chat
            with gr.Tab(f"Knowledge Chat ({chat_config['model']})"):
                if not mcp_available:
                    gr.Markdown(
                        "### ⚠️ MCP Server Not Configured\n\n"
                        "The knowledge base chat requires an MCP server to be configured.\n\n"
                        "Add the `rag-knowledge` MCP server configuration to "
                        "`src/config/settings.local.yaml`. See `settings.yaml` for an example."
                    )
                else:
                    gr.Markdown("### 💬 Chat with Your Knowledge Base")
                    gr.Markdown(
                        "Ask questions about your experience, skills, and projects. "
                        "The AI will search your knowledge base and provide relevant answers."
                    )

                    with gr.Row():
                        with gr.Column(scale=1):
                            chatbot = gr.Chatbot(
                                label="Conversation",
                                height=600,
                                type="messages",
                                show_copy_button=True,
                            )
                            message = gr.Textbox(
                                label="Your Question",
                                placeholder="e.g., What experience do I have with React? Tell me about my GraphQL projects...",
                                show_label=False,
                            )
                            with gr.Row():
                                export_btn = gr.Button("📥 Export to Markdown", size="sm")
                                export_file = gr.File(label="Download", visible=False)

                        with gr.Column(scale=1):
                            context_display = gr.Markdown(
                                label="Retrieved Context",
                                value="*Retrieved context will appear here after you ask a question*",
                            )

                    # State to track full conversation with sources
                    chat_exchanges = gr.State(value=[])

                    # Event handlers for Knowledge Chat
                    def format_context(context_docs):
                        """Format retrieved documents for display."""
                        if not context_docs:
                            return "*No context retrieved*"

                        result = "**📚 Retrieved Context:**\n\n"
                        for doc in context_docs:
                            source = doc.metadata.get("source", "Unknown source")
                            result += f"**Source:** `{source}`\n\n"
                            result += doc.page_content + "\n\n---\n\n"
                        return result

                    def chat(history, exchanges):
                        """Handle chat interaction with RAG."""
                        if not history:
                            return history, "*No context retrieved*", exchanges

                        last_message = history[-1]["content"]
                        prior = history[:-1]
                        answer, context_docs = chat_service.answer_question(
                            last_message, prior
                        )
                        history.append({"role": "assistant", "content": answer})

                        # Track this exchange with its sources
                        exchanges.append(
                            {
                                "question": last_message,
                                "answer": answer,
                                "context_docs": context_docs,
                            }
                        )

                        return history, format_context(context_docs), exchanges

                    def put_message_in_chatbot(message_text, history):
                        """Add user message to chat history."""
                        return "", history + [{"role": "user", "content": message_text}]

                    def export_chat(exchanges):
                        """Export conversation to markdown file."""
                        if not exchanges:
                            return gr.update(visible=False)

                        markdown = "# Knowledge Base Chat Export\n\n"
                        markdown += f"*Exported: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
                        markdown += "---\n\n"

                        for i, exchange in enumerate(exchanges, 1):
                            markdown += f"## Q{i}: {exchange['question']}\n\n"
                            markdown += f"**Answer:**\n\n{exchange['answer']}\n\n"

                            if exchange["context_docs"]:
                                markdown += "**Sources:**\n\n"
                                for doc in exchange["context_docs"]:
                                    source = doc.metadata.get("source", "Unknown source")
                                    markdown += f"- `{source}`\n"
                                    markdown += f"  > {doc.page_content[:200]}...\n\n"

                            markdown += "---\n\n"

                        # Write to temporary file
                        import tempfile

                        with tempfile.NamedTemporaryFile(
                            mode="w", suffix=".md", delete=False
                        ) as f:
                            f.write(markdown)
                            temp_path = f.name

                        return gr.update(value=temp_path, visible=True)

                    message.submit(
                        fn=put_message_in_chatbot,
                        inputs=[message, chatbot],
                        outputs=[message, chatbot],
                    ).then(
                        fn=chat,
                        inputs=[chatbot, chat_exchanges],
                        outputs=[chatbot, context_display, chat_exchanges],
                    )

                    export_btn.click(
                        fn=export_chat,
                        inputs=[chat_exchanges],
                        outputs=[export_file],
                    )

    return app


def launch():
    """Launch the Gradio application."""
    app = create_app()
    app.launch(inbrowser=True)
