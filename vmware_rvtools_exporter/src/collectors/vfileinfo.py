import re
import time
from pyVmomi import vim, vmodl

from .context import CollectorContext
from ..property_fetch import fetch_objects


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger
    config = context.config

    if not config.fileinfo_enabled:
        return []

    # Fetch Datastores
    # Try shared data first
    datastores = context.shared_data.get("datastores")
    
    if not datastores:
        try:
            datastores = fetch_objects(
                context.service_instance, 
                vim.Datastore, 
                ["name", "browser", "summary.accessible"]
            )
        except Exception as exc:
            diagnostics.add_error("vFileInfo", "property_fetch", exc)
            logger.error("Fallo fetching Datastores for vFileInfo: %s", exc)
            return []

    # Sort and Limit Datastores
    # Sort by name stable
    datastores.sort(key=lambda x: x.get("props", {}).get("name", ""))
    
    # Filter accessible only
    accessible_datastores = [
        ds for ds in datastores 
        if ds.get("props", {}).get("summary.accessible", False) and ds.get("props", {}).get("browser")
    ]
    
    target_datastores = accessible_datastores[:config.fileinfo_max_datastores]
    
    rows = []
    
    # Compile regex if provided
    include_regex = re.compile(config.fileinfo_include_pattern) if config.fileinfo_include_pattern else None
    exclude_regex = re.compile(config.fileinfo_exclude_pattern) if config.fileinfo_exclude_pattern else None

    for ds_item in target_datastores:
        ds_name = ds_item.get("props", {}).get("name", "")
        browser = ds_item.get("props", {}).get("browser")
        
        if not browser:
            continue
            
        diagnostics.add_attempt("vFileInfo")
        logger.info(f"Scanning datastore: {ds_name}")
        
        try:
            search_spec = vim.host.DatastoreBrowser.SearchSpec()
            # Reduced query to basic types to avoid compatibility issues
            file_query = [
                vim.host.DatastoreBrowser.FileInfo.Query(),
                vim.host.DatastoreBrowser.FolderInfo.Query()
            ]
            search_spec.query = file_query
            search_spec.details = vim.host.DatastoreBrowser.FileInfo(
                fileType=True, fileSize=True, modification=True, fileOwner=True
            )
            
            # Use datastore path
            ds_path = f"[{ds_name}] {config.fileinfo_path}"
            # Normalize path
            if ds_path.endswith("//"):
                ds_path = ds_path[:-1]

            try:
                task = browser.SearchDatastoreSubFolders_Task(
                    datastorePath=ds_path,
                    searchSpec=search_spec
                )
            except vmodl.fault.InvalidArgument as e:
                # Often happens if path is invalid or browser not supported
                logger.warning(f"InvalidArgument searching {ds_name}: {e}")
                diagnostics.add_error("vFileInfo", ds_name, e)
                continue
            
            # Wait for task with timeout
            start_time = time.time()
            task_state = None
            
            while True:
                try:
                    # Refresh task info? properties usually update on access for ManagedObject? 
                    # No, for Task object in pyVmomi, properties might not auto-update without PropertyCollector.
                    # But accessing .info usually triggers a fetch if it's not cached?
                    # Let's try to access info.state
                    task_state = task.info.state
                except Exception as e:
                    # If we can't read task state, abort
                    logger.warning(f"Failed to read task state for {ds_name}: {e}")
                    task_state = vim.TaskInfo.State.error
                    break

                if task_state in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
                    break
                
                if time.time() - start_time > config.fileinfo_timeout_sec:
                    try:
                        task.CancelTask()
                    except:
                        pass
                    logger.warning(f"Timeout browsing datastore {ds_name}")
                    task_state = "TIMEOUT"
                    break
                time.sleep(0.5)
            
            if task_state == vim.TaskInfo.State.success:
                results = task.info.result
                files_collected = 0
                
                if results:
                    for res in results:
                        if files_collected >= config.fileinfo_max_files_per_datastore:
                            break
                            
                        folder_path = res.folderPath
                        if not folder_path:
                            continue
                            
                        if hasattr(res, "file"):
                            for f in res.file:
                                if files_collected >= config.fileinfo_max_files_per_datastore:
                                    break
                                
                                filename = f.path
                                
                                # Filters
                                if include_regex and not include_regex.search(filename):
                                    continue
                                if exclude_regex and exclude_regex.search(filename):
                                    continue
                                    
                                full_path = f"{folder_path}{filename}" if folder_path.endswith("/") else f"{folder_path}/{filename}"
                                size = getattr(f, "fileSize", 0)
                                mod = getattr(f, "modification", "")
                                if mod:
                                    try:
                                        mod = mod.isoformat()
                                    except:
                                        mod = str(mod)
                                
                                owner = getattr(f, "owner", "")
                                
                                # Map type
                                ftype = f.__class__.__name__
                                if ftype.startswith("FileInfo"): ftype = "File"
                                
                                rows.append({
                                    "Friendly Path Name": ds_name,
                                    "File Name": filename,
                                    "File Type": ftype,
                                    "File Size in bytes": size,
                                    "Path": full_path,
                                    "Internal Sort Column": "",
                                    "VI SDK Server": context.config.server,
                                    "VI SDK UUID": "", # Could get from service content if needed
                                    "Datastore": ds_name, # Extra helpful field
                                    "Modified": mod,
                                    "Owner": owner,
                                    "Type": ftype
                                })
                                files_collected += 1
                
                diagnostics.add_success("vFileInfo")
            
            elif task_state == vim.TaskInfo.State.error:
                msg = task.info.error.msg if task.info.error else "Unknown task error"
                logger.warning(f"Error browsing datastore {ds_name}: {msg}")
                diagnostics.add_error("vFileInfo", ds_name, Exception(msg))
                
        except Exception as exc:
            diagnostics.add_error("vFileInfo", ds_name, exc)
            logger.warning(f"Exception browsing datastore {ds_name}: {exc}")

    return rows
